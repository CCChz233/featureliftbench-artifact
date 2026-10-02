"""Submission revision tracking and source/submission graph comparison."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .builder import GraphBuilder
from .storage import JsonlGraphStore


DEFINITION_KINDS = frozenset(
    {"class", "function", "interface", "interface_method", "method", "type"}
)
_PYTHON_IMPORT_RE = re.compile(r"(?m)^\s*(?:from|import)\s+([A-Za-z_][\w.]*)")
_GO_IMPORT_RE = re.compile(r'(?m)(?:^|\s)"([^"\n]+)"')


def sync_submission(graph_root: Path, submission_dir: Path) -> dict[str, Any]:
    """Create a graph revision only when submission content really changes."""

    root = graph_root.resolve()
    submission = submission_dir.resolve()
    state_path = root / "submission_state.json"
    state = _read_json(state_path)
    content_hash, files = _directory_inventory(submission)
    previous_hash = str(state.get("content_hash", ""))
    revision = int(state.get("revision", 0))
    changed = content_hash != previous_hash
    graph_relative = ""
    if changed:
        revision += 1
        revision_root = root / "submission" / "revisions" / str(revision)
        if revision_root.exists():
            shutil.rmtree(revision_root)
        revision_root.mkdir(parents=True)
        graph_dir = revision_root / "graph"
        if _has_supported_source(submission):
            snapshot = GraphBuilder().build(submission)
            JsonlGraphStore().write(snapshot, graph_dir)
            graph_relative = graph_dir.relative_to(root).as_posix()
        record = {
            "revision": revision,
            "content_hash": content_hash,
            "files": files,
            "graph": graph_relative,
        }
        _write_json(revision_root / "revision.json", record)
        history = state.get("history") if isinstance(state.get("history"), list) else []
        history.append(record)
        state.update(
            {
                "revision": revision,
                "content_hash": content_hash,
                "history": history,
            }
        )
        _write_json(state_path, state)
        claims_path = root / "semantic_claims.jsonl"
        if claims_path.is_file():
            from .ledger import RepoGraphLedger

            RepoGraphLedger(root).invalidate_for_revision(revision)
    elif revision > 0:
        history = state.get("history") if isinstance(state.get("history"), list) else []
        if history and isinstance(history[-1], dict):
            graph_relative = str(history[-1].get("graph", ""))
    result = {
        "schema_version": "featureliftbench.repo_graph.submission_sync.v1",
        "revision": revision,
        "content_hash": content_hash,
        "changed": changed,
        "files": files,
        "graph": graph_relative,
    }
    _write_json(root / "submission_sync.json", result)
    return result


def compare_submission(
    graph_root: Path,
    submission_dir: Path,
    *,
    source_repository: Path | None = None,
) -> dict[str, Any]:
    """Compare task entrypoints and forbidden dependencies against the latest revision."""

    root = graph_root.resolve()
    submission = submission_dir.resolve()
    sync = sync_submission(root, submission)
    base = JsonlGraphStore().load(root / "base")
    overlay = _read_json(root / "task_overlay.json")
    revision_graph = root / str(sync.get("graph", "")) if sync.get("graph") else None
    submission_snapshot = (
        JsonlGraphStore().load(revision_graph)
        if revision_graph is not None and revision_graph.is_dir()
        else None
    )
    source_repo = source_repository or _source_repository_from_env()

    submitted_nodes = submission_snapshot.nodes if submission_snapshot is not None else []
    mappings = []
    matched_submission_ids: set[int] = set()
    missing_providers = []
    for mapping in overlay.get("entrypoint_mapping", []):
        if not isinstance(mapping, dict):
            continue
        source_payload = mapping.get("node")
        entrypoint = str(mapping.get("entrypoint", ""))
        if not isinstance(source_payload, dict):
            missing_providers.append(entrypoint)
            mappings.append(
                {"entrypoint": entrypoint, "classification": "missing", "reason": "unmapped source"}
            )
            continue
        source_node = base.nodes[int(source_payload["id"]) - 1]
        candidates = [
            node
            for node in submitted_nodes
            if node.name == source_node.name and node.kind == source_node.kind
        ]
        if not candidates:
            candidates = [node for node in submitted_nodes if node.name == source_node.name]
        if not candidates:
            missing_providers.append(entrypoint)
            mappings.append(
                {
                    "entrypoint": entrypoint,
                    "source": source_node.stable_id,
                    "classification": "missing",
                }
            )
            continue
        target = sorted(candidates, key=lambda node: (node.qualified_name, node.stable_id))[0]
        matched_submission_ids.add(target.id)
        classification = _classify_mapping(
            source_node,
            target,
            source_repository=source_repo,
            submission_repository=submission,
        )
        mappings.append(
            {
                "entrypoint": entrypoint,
                "source": source_node.stable_id,
                "submission": target.stable_id,
                "classification": classification,
            }
        )

    new_artifacts = [
        {
            "submission": node.stable_id,
            "classification": "new",
        }
        for node in submitted_nodes
        if node.kind in DEFINITION_KINDS and node.id not in matched_submission_ids
    ]
    forbidden_hits = _forbidden_import_hits(
        submission,
        [str(item) for item in overlay.get("forbidden_imports", []) if isinstance(item, str)],
    )
    expected_types = [
        mapping["entrypoint"]
        for mapping in mappings
        if mapping.get("classification") == "missing"
        and _source_mapping_kind(mapping, base) in {"class", "interface", "type"}
    ]
    missing_resources = _missing_resource_candidates(base, submission)
    result = {
        "schema_version": "featureliftbench.repo_graph.submission_compare.v1",
        "revision": sync["revision"],
        "content_hash": sync["content_hash"],
        "artifact_mappings": mappings + new_artifacts,
        "classification_counts": _classification_counts(mappings + new_artifacts),
        "gaps": {
            "missing_providers": missing_providers,
            "missing_types": expected_types,
            "forbidden_imports": forbidden_hits,
            "missing_resources": missing_resources,
        },
        "advisory_only": True,
    }
    _write_json(root / "submission_compare.json", result)
    return result


def _classify_mapping(
    source: Any,
    target: Any,
    *,
    source_repository: Path | None,
    submission_repository: Path,
) -> str:
    source_bytes = _node_bytes(source, source_repository)
    target_bytes = _node_bytes(target, submission_repository)
    if source_bytes is not None and target_bytes is not None and source_bytes == target_bytes:
        return "copied"
    source_signature = str(source.attributes.get("signature", "")).strip()
    target_signature = str(target.attributes.get("signature", "")).strip()
    if source_signature and source_signature == target_signature:
        return "adapted"
    return "rewritten"


def _node_bytes(node: Any, repository: Path | None) -> bytes | None:
    if repository is None or node.span is None:
        return None
    path = repository / node.span.path
    if not path.is_file():
        return None
    content = path.read_bytes()
    if node.span.end_byte > len(content):
        return None
    return content[node.span.start_byte : node.span.end_byte]


def _source_mapping_kind(mapping: dict[str, Any], base: Any) -> str:
    source_id = mapping.get("source")
    if not isinstance(source_id, str):
        return ""
    for node in base.nodes:
        if node.stable_id == source_id:
            return node.kind
    return ""


def _missing_resource_candidates(base: Any, submission: Path) -> list[str]:
    submission_names = {path.name for path in submission.rglob("*") if path.is_file()}
    missing = []
    for node in base.nodes:
        if node.kind != "resource":
            continue
        name = Path(node.name).name
        if name and name not in submission_names:
            missing.append(node.qualified_name)
    return sorted(set(missing))[:100]


def _forbidden_import_hits(submission: Path, forbidden: list[str]) -> list[dict[str, str]]:
    roots = {item.split(".", 1)[0] for item in forbidden if item}
    hits = []
    for path in sorted(submission.rglob("*")) if submission.is_dir() else []:
        if not path.is_file() or path.suffix not in {".py", ".pyi", ".go"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        imports = (
            [match.group(1) for match in _PYTHON_IMPORT_RE.finditer(text)]
            if path.suffix in {".py", ".pyi"}
            else [match.group(1) for match in _GO_IMPORT_RE.finditer(text)]
        )
        for imported in imports:
            if imported.split(".", 1)[0] in roots:
                hits.append(
                    {
                        "path": path.relative_to(submission).as_posix(),
                        "import": imported,
                    }
                )
    return hits


def _classification_counts(mappings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for mapping in mappings:
        classification = str(mapping.get("classification", "unknown"))
        counts[classification] = counts.get(classification, 0) + 1
    return dict(sorted(counts.items()))


def _directory_inventory(root: Path) -> tuple[str, list[dict[str, Any]]]:
    digest = hashlib.sha256()
    files = []
    if not root.is_dir():
        return digest.hexdigest(), files
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(bytes.fromhex(content_hash))
        files.append({"path": relative, "sha256": content_hash, "bytes": len(content)})
    return digest.hexdigest(), files


def _has_supported_source(root: Path) -> bool:
    return root.is_dir() and any(
        path.is_file() and path.suffix in {".py", ".pyi", ".go"} for path in root.rglob("*")
    )


def _source_repository_from_env() -> Path | None:
    workspace = os.environ.get("FEATURELIFTBENCH_WORKSPACE", "").strip()
    if not workspace:
        return None
    candidate = Path(workspace) / "repo"
    return candidate.resolve() if candidate.is_dir() else None


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
