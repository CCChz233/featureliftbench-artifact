"""Run-local RSG initialization, cache materialization, and audit lifecycle."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import resource
import shutil
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .builder import GraphBuilder
from .detectors import detect_runtime_risks
from .hashing import canonical_json, digest_json
from .policy import (
    BUDGET_TOKENS_ENV,
    CACHE_DIR_ENV,
    INSPECT_MAX_CHARS_ENV,
    QUERY_MAX_CHARS_ENV,
    ROOT_ENV,
    RepoGraphPolicy,
)
from .protocol import dumps_response, response_payload
from .query import DEPENDENCY_EDGE_KINDS, GraphQueryEngine
from .ledger import RepoGraphLedger
from .storage import JsonlGraphStore


RUN_SCHEMA_VERSION = "featureliftbench.repo_graph.run.v1"
PROMPT_MARKER = "## Repository Semantic Graph (RSG)"


@dataclass(frozen=True)
class RepoGraphRunState:
    policy: RepoGraphPolicy
    root: Path
    base: Path
    bootstrap_path: Path
    source_repository: Path
    initial_artifact_hashes: dict[str, str]
    env: dict[str, str]


def initialize_repo_graph(
    *,
    workspace_dir: Path,
    agent_output_dir: Path,
    config_env: Mapping[str, str] | None,
) -> RepoGraphRunState | None:
    """Initialize an enabled graph before an Agent is allowed to run."""

    policy = RepoGraphPolicy.from_env(config_env)
    if not policy.enabled:
        return None

    started = time.monotonic()
    rss_before = _peak_rss_bytes()
    workspace = workspace_dir.resolve()
    agent_output = agent_output_dir.resolve()
    repository = workspace / "repo"
    metadata_path = workspace / "metadata.json"
    public_tests = workspace / "public_tests"
    if not repository.is_dir():
        raise ValueError(f"repository graph source is missing: {repository}")
    if not metadata_path.is_file():
        raise ValueError(f"repository graph metadata is missing: {metadata_path}")

    root = agent_output / "state" / "repo_graph"
    base = root / "base"
    root.mkdir(parents=True, exist_ok=False)
    _write_json(agent_output / "repo_graph_policy.json", policy.to_dict())

    builder = GraphBuilder()
    fingerprint = builder.fingerprint(repository)
    snapshot_id = str(fingerprint["snapshot_id"])
    cache_root = _cache_root(agent_output, config_env)
    cache_entry = cache_root / snapshot_id
    cache_hit = _ensure_cached_snapshot(
        builder=builder,
        repository=repository,
        fingerprint=fingerprint,
        cache_entry=cache_entry,
    )
    shutil.copytree(cache_entry, base)
    snapshot = JsonlGraphStore().load(base)
    if snapshot.manifest.get("snapshot_id") != snapshot_id:
        raise ValueError("materialized graph snapshot does not match its cache identity")
    self_check = GraphQueryEngine(snapshot).self_check()
    if not self_check.get("valid"):
        raise ValueError(f"repository graph self-check failed: {self_check.get('errors', [])}")

    metadata = _read_json(metadata_path)
    _validate_input_scope(repository, metadata_path, public_tests, workspace)
    overlay = _build_task_overlay(
        metadata=metadata,
        public_tests_dir=public_tests,
        engine=GraphQueryEngine(snapshot),
        mode=policy.mode,
    )
    _write_json(root / "task_overlay.json", overlay)
    closure_overlay: dict[str, Any] | None = None
    if policy.mode in {"closure", "evidence"}:
        closure_overlay = _build_closure_overlay(overlay, GraphQueryEngine(snapshot))
        _write_json(root / "closure_overlay.json", closure_overlay)
        _write_closure_views(root, overlay, closure_overlay)
    if policy.mode == "evidence":
        ledger = RepoGraphLedger(root)
        ledger.initialize()
        _write_json(
            root / "risk_detectors.json",
            detect_runtime_risks(snapshot, task_overlay=overlay),
        )

    submission_state = {
        "schema_version": "featureliftbench.repo_graph.submission_state.v1",
        "revision": 0,
        "content_hash": _directory_digest(workspace / "submission"),
        "history": [],
    }
    _write_json(root / "submission_state.json", submission_state)
    (agent_output / "repo_graph_queries.jsonl").touch()

    bootstrap = _build_bootstrap(
        engine=GraphQueryEngine(snapshot),
        overlay=overlay,
        closure=closure_overlay,
        policy=policy,
    )
    bootstrap_path = root / "bootstrap.md"
    bootstrap_path.write_text(bootstrap, encoding="utf-8")

    initial_hashes = _immutable_artifact_hashes(root)
    build_record = {
        "schema_version": RUN_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "graph_hash": snapshot.manifest.get("graph_hash"),
        "source_tree_hash": fingerprint.get("source_tree_hash"),
        "source_identity": {
            key: metadata.get("source", {}).get(key, "")
            for key in ("name", "commit")
            if isinstance(metadata.get("source"), dict)
        },
        "builder": fingerprint.get("builder"),
        "counts": snapshot.manifest.get("counts", {}),
        "cache": {
            "hit": cache_hit,
            "key": snapshot_id,
            "materialization": "private-copy",
            "cache_exposed_to_agent": False,
        },
        "input_scope": {
            "repository": "workspace/repo",
            "metadata": "workspace/metadata.json",
            "public_tests": "workspace/public_tests",
            "hidden_test_inputs": 0,
            "evaluation_inputs": 0,
            "reference_solution_inputs": 0,
        },
        "self_check": self_check,
        "duration_seconds": round(time.monotonic() - started, 6),
        "graph_bytes": _directory_bytes(base),
        "rss_peak_bytes": _peak_rss_bytes(),
        "rss_delta_bytes": max(0, _peak_rss_bytes() - rss_before),
    }
    if "entrypoint_mapping" in overlay:
        build_record["entrypoint_mapping"] = overlay["entrypoint_mapping"]
    _write_json(agent_output / "repo_graph_build.json", build_record)
    _write_json(
        agent_output / "repo_graph_usage.json",
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "initialized",
            "snapshot_id": snapshot_id,
            "query_count": 0,
            "successful_query_count": 0,
            "query_failure_count": 0,
            "query_chars": 0,
            "bootstrap_chars": len(bootstrap),
            "task_closure_queried": False,
            "fresh_submission_check": False,
            "adoption_compliant": False,
            "optional_tool_used": False,
            "support_queried": False,
            "search_queried": False,
            "inspect_queried": False,
            "mechanism_status": "not_queried",
            "protocol_violation": False,
            "rsg_bootstrap": policy.bootstrap,
            "rsg_budget_tokens": policy.budget_tokens,
        },
    )
    return RepoGraphRunState(
        policy=policy,
        root=root,
        base=base,
        bootstrap_path=bootstrap_path,
        source_repository=repository,
        initial_artifact_hashes=initial_hashes,
        env={
            ROOT_ENV: str(root),
            QUERY_MAX_CHARS_ENV: str(policy.query_max_chars),
            INSPECT_MAX_CHARS_ENV: str(policy.inspect_max_chars),
            BUDGET_TOKENS_ENV: str(policy.budget_tokens),
        },
    )


def append_repo_graph_prompt(task_file: Path, state: RepoGraphRunState) -> None:
    """Append one byte-identical graph contract to the task seen by every adapter."""

    original = task_file.read_text(encoding="utf-8")
    if PROMPT_MARKER in original:
        raise ValueError("repository graph prompt marker already exists in TASK.md")
    appendix = state.bootstrap_path.read_text(encoding="utf-8")
    task_file.write_text(original.rstrip() + "\n\n" + appendix.rstrip() + "\n", encoding="utf-8")


def finalize_repo_graph(state: RepoGraphRunState, *, submission_dir: Path) -> dict[str, Any]:
    """Perform a read-only post-run integrity and submission-delta audit."""

    from .submission import compare_submission, sync_submission

    final_hashes = _immutable_artifact_hashes(state.root)
    graph_modified = final_hashes != state.initial_artifact_hashes
    sync = sync_submission(state.root, submission_dir)
    comparison = compare_submission(
        state.root,
        submission_dir,
        source_repository=state.source_repository,
    )
    query_rows, invalid_query_rows = _read_jsonl(
        state.root.parent.parent / "repo_graph_queries.jsonl"
    )
    valid_query_rows = [row for row in query_rows if _valid_query_audit_row(row)]
    invalid_query_rows += len(query_rows) - len(valid_query_rows)
    query_rows = valid_query_rows
    query_chars = sum(int(row.get("response_chars", 0)) for row in query_rows)
    successful_rows = [row for row in query_rows if row.get("status", "success") == "success"]
    failure_rows = [row for row in query_rows if row.get("status") == "failed"]
    successful_commands = {
        str(row.get("command")) for row in successful_rows if row.get("command")
    }
    task_closure_queried = "task-closure" in successful_commands
    support_queried = "support" in successful_commands
    search_queried = "search" in successful_commands
    inspect_queried = "inspect" in successful_commands
    optional_tool_used = bool(
        successful_commands
        & {"search", "inspect", "support", "task-closure", "closure", "paths", "risks"}
    )
    final_revision = int(sync.get("revision", 0))
    fresh_submission_check = any(
        row.get("command") == "submission-check"
        and row.get("revision") == final_revision
        for row in successful_rows
    )
    # Legacy pilot field: historical forced gate. Formal v2 treats optional tool
    # use as observational only (never a suite blocker).
    adoption_compliant = optional_tool_used
    evidence_audit: dict[str, Any] = {}
    if (state.root / "semantic_claims.jsonl").is_file():
        ledger = RepoGraphLedger(state.root)
        evidence_audit = {
            "freshness": ledger.freshness_report(),
            "stopping_guard": ledger.stopping_guard(),
            "runner_role": "post_run_advisory_audit",
            "native_online_enforcement_observed": (
                state.root / "stopping_guard.json"
            ).is_file(),
        }
    if graph_modified or invalid_query_rows > 0:
        mechanism_status = "protocol_violation"
    elif optional_tool_used:
        mechanism_status = "optional_tools_used"
    else:
        mechanism_status = "not_queried"
    usage = {
        "schema_version": RUN_SCHEMA_VERSION,
        "status": "finalized",
        "snapshot_id": _read_json(state.base / "manifest.json").get("snapshot_id"),
        "query_count": len(query_rows),
        "successful_query_count": len(successful_rows),
        "query_failure_count": len(failure_rows),
        "query_chars": query_chars,
        "bootstrap_chars": len(state.bootstrap_path.read_text(encoding="utf-8")),
        "submission_revision": final_revision,
        "submission_changed": sync.get("changed", False),
        "submission_gaps": comparison.get("gaps", {}),
        "protocol_violation": graph_modified or invalid_query_rows > 0,
        "protocol_violations": (
            (["immutable_graph_artifact_modified"] if graph_modified else [])
            + (["invalid_query_audit_row"] if invalid_query_rows else [])
        ),
        "invalid_query_audit_rows": invalid_query_rows,
        "task_closure_queried": task_closure_queried,
        "fresh_submission_check": fresh_submission_check,
        "support_queried": support_queried,
        "search_queried": search_queried,
        "inspect_queried": inspect_queried,
        "optional_tool_used": optional_tool_used,
        "adoption_compliant": adoption_compliant,
        "mechanism_status": mechanism_status,
        "rsg_bootstrap": state.policy.bootstrap,
        "rsg_budget_tokens": state.policy.budget_tokens,
        "evidence_control": evidence_audit,
    }
    _write_json(state.root.parent.parent / "repo_graph_usage.json", usage)
    return usage


def _cache_root(agent_output: Path, config_env: Mapping[str, str] | None) -> Path:
    configured = (config_env or {}).get(CACHE_DIR_ENV, "").strip()
    return Path(configured).resolve() if configured else agent_output.parent.parent / ".repo_graph_cache"


def prewarm_repo_graph(repository: Path, cache_root: Path) -> dict[str, Any]:
    """Materialize one graph cache entry without exposing any task-private inputs."""

    started = time.monotonic()
    rss_before = _peak_rss_bytes()
    builder = GraphBuilder()
    repository_path = repository.resolve()
    fingerprint = builder.fingerprint(repository_path)
    snapshot_id = str(fingerprint["snapshot_id"])
    cache_entry = cache_root.resolve() / snapshot_id
    cache_hit = _ensure_cached_snapshot(
        builder=builder,
        repository=repository_path,
        fingerprint=fingerprint,
        cache_entry=cache_entry,
    )
    snapshot = JsonlGraphStore().load(cache_entry)
    return {
        "snapshot_id": snapshot_id,
        "graph_hash": snapshot.manifest.get("graph_hash"),
        "cache_hit": cache_hit,
        "duration_seconds": round(time.monotonic() - started, 6),
        "graph_bytes": _directory_bytes(cache_entry),
        "rss_peak_bytes": _peak_rss_bytes(),
        "rss_delta_bytes": max(0, _peak_rss_bytes() - rss_before),
        "counts": snapshot.manifest.get("counts", {}),
    }


def _validate_input_scope(
    repository: Path,
    metadata: Path,
    public_tests: Path,
    workspace: Path,
) -> None:
    blocked_parts = {"hidden_tests", "evaluation", "reference_solution"}
    paths = [repository, metadata]
    if public_tests.exists():
        paths.append(public_tests)
    for path in paths:
        try:
            relative = path.resolve().relative_to(workspace.resolve())
        except ValueError as exc:
            raise ValueError(f"repository graph input escapes redacted workspace: {path}") from exc
        if blocked_parts.intersection(relative.parts):
            raise ValueError(f"repository graph input crosses private evaluation boundary: {relative}")


def _ensure_cached_snapshot(
    *,
    builder: GraphBuilder,
    repository: Path,
    fingerprint: dict[str, object],
    cache_entry: Path,
) -> bool:
    cache_entry.parent.mkdir(parents=True, exist_ok=True)
    lock_path = cache_entry.parent / f".{cache_entry.name}.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if _valid_cache_entry(cache_entry, str(fingerprint["snapshot_id"])):
            return True
        if cache_entry.exists():
            shutil.rmtree(cache_entry)
        temporary = Path(tempfile.mkdtemp(prefix=f".{cache_entry.name}.", dir=cache_entry.parent))
        try:
            snapshot = builder.build(repository)
            if snapshot.manifest.get("snapshot_id") != fingerprint["snapshot_id"]:
                raise ValueError("repository changed while graph snapshot was being built")
            JsonlGraphStore().write(snapshot, temporary)
            JsonlGraphStore().load(temporary)
            os.replace(temporary, cache_entry)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return False


def _valid_cache_entry(path: Path, expected_snapshot_id: str) -> bool:
    if not path.is_dir():
        return False
    try:
        snapshot = JsonlGraphStore().load(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return snapshot.manifest.get("snapshot_id") == expected_snapshot_id


def _build_task_overlay(
    *,
    metadata: dict[str, Any],
    public_tests_dir: Path,
    engine: GraphQueryEngine,
    mode: str,
) -> dict[str, Any]:
    feature = metadata.get("feature") if isinstance(metadata.get("feature"), dict) else {}
    output = metadata.get("output") if isinstance(metadata.get("output"), dict) else {}
    environment = (
        metadata.get("environment") if isinstance(metadata.get("environment"), dict) else {}
    )
    entrypoints = _string_list(feature.get("source_entrypoints"))
    has_source_hints = "source_entrypoints" in feature
    behaviors = _string_list(feature.get("included_behaviors"))
    mappings = [_map_entrypoint(entrypoint, engine) for entrypoint in entrypoints]
    public_inventory = []
    if public_tests_dir.is_dir():
        for path in sorted(public_tests_dir.rglob("*")):
            if path.is_file():
                content = path.read_bytes()
                public_inventory.append(
                    {
                        "path": path.relative_to(public_tests_dir).as_posix(),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content),
                    }
                )
    payload = {
        "schema_version": "featureliftbench.repo_graph.task_overlay.v1",
        "task_id": metadata.get("task_id", ""),
        "mode": mode,
        "behaviors": [
            {"id": f"behavior:B{index:03d}", "description": behavior}
            for index, behavior in enumerate(behaviors, start=1)
        ],
        "output_api": {
            key: output.get(key, "")
            for key in ("package", "import", "callable", "module", "signature", "symbols")
            if key in output
        },
        "forbidden_imports": _string_list(environment.get("forbidden_imports")),
        "environment_scope": {
            key: environment.get(key)
            for key in (
                "python",
                "go",
                "network",
                "cgo_enabled",
                "module_path",
                "allowed_dependencies",
            )
            if key in environment
        },
        "public_tests": public_inventory,
        "private_to_run": True,
        "agent_claim_required": True,
    }
    if has_source_hints:
        payload["source_entrypoints"] = entrypoints
        payload["entrypoint_mapping"] = mappings
    payload["overlay_digest"] = digest_json(payload)
    return payload


def _map_entrypoint(entrypoint: str, engine: GraphQueryEngine) -> dict[str, Any]:
    candidates = engine.search(entrypoint, limit=10)["matches"]
    if not candidates:
        candidates = engine.search(entrypoint.rsplit(".", 1)[-1], limit=10)["matches"]
    best = candidates[0] if candidates else None
    return {
        "entrypoint": entrypoint,
        "status": "mapped" if best else "unmapped",
        "node": best,
        "alternatives": candidates[1:5] if best else [],
    }


def _build_closure_overlay(overlay: dict[str, Any], engine: GraphQueryEngine) -> dict[str, Any]:
    roots = []
    for mapping in overlay.get("entrypoint_mapping", []):
        node = mapping.get("node") if isinstance(mapping, dict) else None
        if isinstance(node, dict) and isinstance(node.get("stable_id"), str):
            resolved = engine.index.resolve_node(node["stable_id"])
            if resolved is not None:
                roots.append(resolved)
    queue = deque(node.id for node in roots)
    visited: set[int] = set()
    exact_edges = []
    risks = []
    while queue and len(visited) < 200:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for edge in engine.index.outgoing[current]:
            if edge.kind not in DEPENDENCY_EDGE_KINDS:
                continue
            if edge.resolution == "exact" and edge.target is not None:
                exact_edges.append(engine._compact_edge(edge))
                if edge.target not in visited:
                    queue.append(edge.target)
            else:
                risks.append(engine._compact_edge(edge))
    payload = {
        "schema_version": "featureliftbench.repo_graph.closure_overlay.v1",
        "candidate_nodes": [
            engine._compact_node(engine.index.nodes_by_id[node_id]) for node_id in sorted(visited)
        ],
        "exact_edges": exact_edges,
        "uncertain_risks": risks[:100],
        "truncated": bool(queue) or len(risks) > 100,
        "classification": "candidate_only",
        "agent_claim_required": True,
    }
    if "source_entrypoints" in overlay:
        payload["entrypoints"] = [node.stable_id for node in roots]
    payload["closure_digest"] = digest_json(payload)
    return payload


def _write_closure_views(
    root: Path,
    overlay: dict[str, Any],
    closure: dict[str, Any],
) -> None:
    lines = [
        "# RSG Closure Candidate",
        "",
        "This is an advisory exact-edge candidate, not a completed closure claim.",
        "The Agent must classify required, replaceable, incidental, optional, or excluded artifacts.",
    ]
    if "source_entrypoints" in overlay:
        lines.extend(["", "## Entrypoints"])
        lines.extend(f"- `{item}`" for item in closure.get("entrypoints", []))
    lines.extend(["", "## Candidate nodes"])
    for node in closure.get("candidate_nodes", [])[:100]:
        lines.append(f"- `{node.get('stable_id', '')}`")
    (root / "closure_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    dependency_manifest = {
        "schema_version": "featureliftbench.repo_graph.dependency_manifest.v1",
        "task_id": overlay.get("task_id", ""),
        "candidate_nodes": closure.get("candidate_nodes", []),
        "uncertain_risks": closure.get("uncertain_risks", []),
        "agent_claim_required": True,
    }
    if "source_entrypoints" in overlay:
        dependency_manifest["source_entrypoints"] = overlay["source_entrypoints"]
    _write_json(root / "dependency_manifest.json", dependency_manifest)


def _build_bootstrap(
    *,
    engine: GraphQueryEngine,
    overlay: dict[str, Any],
    closure: dict[str, Any] | None,
    policy: RepoGraphPolicy,
) -> str:
    """Build the optional-tool contract appended to TASK.md (Design v2)."""

    del closure  # retained for call-site compatibility; formal path no longer injects it
    if policy.bootstrap == "auto_support":
        return _build_auto_support_bootstrap(engine=engine, overlay=overlay, policy=policy)

    # tool_only: short contract + strong usage cue for hard failures.
    seed_name = (
        "task entrypoint"
        if "source_entrypoints" in overlay
        else "candidate symbol you locate from the functional contract"
    )
    prefix = (
        f"{PROMPT_MARKER}\n\n"
        "A deterministic repository fact graph is available as **optional** advisory tools.\n"
        "- `flb-rsg search <query>`\n"
        "- `flb-rsg inspect <stable_id>`\n"
        "- `flb-rsg support --seed <stable_id_or_name> [--budget-tokens N]`\n\n"
        f"Efficiency cue: after identifying a {seed_name}, prefer "
        "`flb-rsg support --seed <symbol>` once before broad recursive search. "
        "Use support again when public tests fail on missing API, config, resource, "
        "or registry/dispatch behavior. Source code remains authoritative; "
        "probable edges are hypotheses. Do not edit graph files.\n\n"
        f"Mode: `{policy.mode}`. Bootstrap: `{policy.bootstrap}`. "
        f"Default support budget: `{policy.budget_tokens}` tokens. "
        f"Query responses capped at {policy.query_max_chars} characters "
        f"(inspect default: {policy.inspect_max_chars}).\n"
    )
    if len(prefix) > policy.bootstrap_max_chars:
        raise ValueError("repo graph bootstrap exceeded configured character budget")
    return prefix


def _build_auto_support_bootstrap(
    *,
    engine: GraphQueryEngine,
    overlay: dict[str, Any],
    policy: RepoGraphPolicy,
) -> str:
    from .support import build_operational_support, render_compact_guidance

    seeds = _seeds_from_overlay(overlay)
    header = (
        f"{PROMPT_MARKER}\n\n"
        "**Token-efficient workflow (follow this):**\n"
        "1. Open ONLY the files listed under start-here below.\n"
        "2. Do not run broad `find`/`grep`/recursive listing of the whole repo first.\n"
        "3. Implement from those files; expand search only after public tests fail.\n"
        "4. If failures mention missing API/config/resource/dispatch, run "
        "`flb-rsg support --seed <entrypoint>` once and continue.\n"
        "Source remains authoritative. Do not edit graph files.\n\n"
        f"Mode: `{policy.mode}`. Bootstrap: `auto_support`. "
        f"Budget: `{policy.budget_tokens}` tokens.\n\n"
    )
    if not seeds:
        rendered = header + (
            "`auto_support` has no preselected seed in this arm; locate a candidate "
            "symbol from the contract, then call `flb-rsg support --seed ...` yourself.\n"
        )
        if len(rendered) > policy.bootstrap_max_chars:
            raise ValueError("repo graph bootstrap exceeded configured character budget")
        return rendered

    support_result = build_operational_support(
        engine,
        seeds,
        budget_tokens=min(policy.budget_tokens, 4_000),
        max_nodes=max(policy.bootstrap_max_nodes * 2, 40),
    )
    guidance = render_compact_guidance(support_result)
    # Keep a tiny JSON appendix for machine use if space remains.
    compact_json = {
        "seeds": support_result.get("seeds"),
        "guidance": support_result.get("guidance"),
        "covered_categories": support_result.get("covered_categories"),
        "status": support_result.get("status"),
    }
    appendix = (
        "\n<details><summary>RSG support summary (compact)</summary>\n\n```json\n"
    )
    suffix = "\n```\n</details>\n"
    remaining = policy.bootstrap_max_chars - len(header) - len(guidance) - len(appendix) - len(suffix)
    if remaining < 256:
        rendered = header + guidance
    else:
        payload = response_payload(
            command="support",
            snapshot_id=engine.snapshot.manifest.get("snapshot_id"),
            result=compact_json,
            max_chars=remaining,
        )
        rendered = header + guidance + appendix + dumps_response(payload) + suffix
    if len(rendered) > policy.bootstrap_max_chars:
        # Last resort: guidance only.
        rendered = (header + guidance)[: policy.bootstrap_max_chars]
    return rendered


def _seeds_from_overlay(overlay: dict[str, Any]) -> list[str]:
    seeds: list[str] = []
    for item in overlay.get("entrypoint_mapping", []):
        if not isinstance(item, dict):
            continue
        node = item.get("node") if isinstance(item.get("node"), dict) else {}
        stable_id = node.get("stable_id")
        if isinstance(stable_id, str) and stable_id.strip():
            seeds.append(stable_id.strip())
            continue
        entrypoint = item.get("entrypoint")
        if isinstance(entrypoint, str) and entrypoint.strip():
            seeds.append(entrypoint.strip())
    if seeds:
        return seeds
    for entrypoint in overlay.get("source_entrypoints", []):
        if isinstance(entrypoint, str) and entrypoint.strip():
            seeds.append(entrypoint.strip())
    return seeds


def task_closure_result(
    *,
    engine: GraphQueryEngine,
    overlay: dict[str, Any],
    closure: dict[str, Any] | None,
    max_files: int = 30,
) -> dict[str, Any]:
    """Return a task-focused, production-first closure view for prompt and CLI use."""

    entrypoint_mappings: dict[str, dict[str, Any]] = {}
    explicit_paths: set[str] = set()
    for item in overlay.get("entrypoint_mapping", []):
        if not isinstance(item, dict):
            continue
        entrypoint = str(item.get("entrypoint", ""))
        node = item.get("node") if isinstance(item.get("node"), dict) else {}
        location = str(node.get("location", ""))
        path = _location_path(location)
        if path:
            explicit_paths.add(path)
        entrypoint_mappings[entrypoint] = {
            "status": item.get("status", "unmapped"),
            "stable_id": node.get("stable_id"),
            "location": location or None,
        }

    closure_value = closure or {
        "candidate_nodes": [],
        "exact_edges": [],
        "uncertain_risks": [],
        "truncated": False,
    }
    nodes_by_graph_id: dict[int, dict[str, Any]] = {}
    grouped: dict[str, dict[str, Any]] = {}
    dependencies: list[dict[str, Any]] = []
    for node in closure_value.get("candidate_nodes", []):
        if not isinstance(node, dict) or not isinstance(node.get("id"), int):
            continue
        nodes_by_graph_id[node["id"]] = node
        path = _location_path(str(node.get("location", "")))
        if not path or (_excluded_bootstrap_path(path) and path not in explicit_paths):
            continue
        record = grouped.setdefault(
            path,
            {"path": path, "entrypoint": path in explicit_paths, "symbols": []},
        )
        symbol = node.get("qualified_name") or node.get("name")
        if symbol and symbol not in record["symbols"]:
            record["symbols"].append(symbol)

    for edge in closure_value.get("exact_edges", []):
        if not isinstance(edge, dict):
            continue
        source = nodes_by_graph_id.get(edge.get("source"))
        target = nodes_by_graph_id.get(edge.get("target"))
        if not source or not target:
            continue
        path = _location_path(str(source.get("location", "")))
        if path not in grouped:
            continue
        dependencies.append(
            {
                "from": source.get("stable_id"),
                "kind": edge.get("kind"),
                "to": target.get("stable_id"),
            }
        )

    relevant_risks: list[dict[str, Any]] = []
    for edge in closure_value.get("uncertain_risks", []):
        if not isinstance(edge, dict):
            continue
        source = nodes_by_graph_id.get(edge.get("source"))
        if not source:
            continue
        path = _location_path(str(source.get("location", "")))
        if path not in grouped:
            continue
        risk = {
            "source": source.get("stable_id"),
            "kind": edge.get("kind"),
            "resolution": edge.get("resolution"),
            "attributes": edge.get("attributes", {}),
        }
        relevant_risks.append(risk)

    files = sorted(
        grouped.values(),
        key=lambda item: (not bool(item["entrypoint"]), str(item["path"])),
    )[:max_files]
    for item in files:
        item["symbols"] = item["symbols"][:12]
    return {
        "task_id": overlay.get("task_id", ""),
        "entrypoint_mappings": entrypoint_mappings,
        "files": files,
        "dependencies": dependencies[:100],
        "dynamic_risks": relevant_risks[:50],
        "closure_truncated": bool(closure_value.get("truncated")),
        "classification": "candidate_only",
        "authority": "source_and_runtime",
    }


def _location_path(location: str) -> str:
    return location.rsplit(":", 1)[0] if ":" in location else location


def _excluded_bootstrap_path(path: str) -> bool:
    lowered = {part.lower() for part in Path(path).parts}
    return bool(
        lowered.intersection(
            {"test", "tests", "doc", "docs", "benchmark", "benchmarks", "microbenchmarks"}
        )
    )


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _immutable_artifact_hashes(root: Path) -> dict[str, str]:
    immutable_names = {
        "bootstrap.md",
        "closure_overlay.json",
        "closure_plan.md",
        "dependency_manifest.json",
        "task_overlay.json",
        "risk_detectors.json",
    }
    result = {
        f"base/{name}": digest
        for name, digest in _artifact_hashes(root / "base").items()
    }
    for name in sorted(immutable_names):
        path = root / name
        if path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1_024


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file():
        return [], 0
    rows = []
    invalid = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if isinstance(value, dict):
                rows.append(value)
            else:
                invalid += 1
    return rows, invalid


def _valid_query_audit_row(row: dict[str, Any]) -> bool:
    digest_fields = (row.get("parameter_digest"), row.get("result_digest"))
    return bool(
        row.get("schema_version") == "featureliftbench.repo_graph.query.v1"
        and isinstance(row.get("command"), str)
        and row.get("status") in {"success", "failed"}
        and isinstance(row.get("revision"), int)
        and row.get("revision", -1) >= 0
        and isinstance(row.get("response_chars"), int)
        and row.get("response_chars", -1) >= 0
        and isinstance(row.get("result"), dict)
        and all(
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
            for value in digest_fields
        )
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
