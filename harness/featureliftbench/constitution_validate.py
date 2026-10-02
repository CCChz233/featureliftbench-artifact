"""Constitution validators for compliant FeatureLiftBench tasks."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from .task_render import (
    COMPLETE_FEATURE_RESPONSIBILITY_HEADING,
    COMPLETE_FEATURE_RESPONSIBILITY_MARKER,
    render_agent_workspace_task,
    render_public_task,
)
from .task_spec import (
    SPEC_STATUS_COMPLIANT,
    SPEC_STATUS_LEGACY,
    compute_generated_task_hash,
    compute_spec_hash,
    get_spec_status,
    load_evaluation_spec,
    load_public_spec,
    validate_evaluation_spec_shape,
    validate_public_spec_shape,
)

PRIVATE_METADATA_KEYS = {
    "evaluation_spec",
    "entanglement",
    "spec_hash",
    "generated_task_hash",
    "task_revision",
}

# Standard module/package metadata used by isolation and provenance checks is
# not part of the task's public feature API. Keep this allowlist narrow so
# project-defined dunder exports such as ``__version__`` still require an
# explicit contract declaration.
STANDARD_MODULE_METADATA_REFS = {
    "featurelifted.__cached__",
    "featurelifted.__doc__",
    "featurelifted.__file__",
    "featurelifted.__loader__",
    "featurelifted.__name__",
    "featurelifted.__package__",
    "featurelifted.__path__",
    "featurelifted.__spec__",
}


def validate_constitution(
    task_dir: Path,
    metadata: dict[str, Any],
    *,
    task_markdown: str | None = None,
    additional_test_nodeids: set[str] | None = None,
    test_source_overrides: dict[str, str] | None = None,
    ignore_test_api_usage: bool = False,
) -> list[str]:
    status = get_spec_status(metadata)
    if status == SPEC_STATUS_LEGACY:
        return _legacy_warnings(metadata)

    errors: list[str] = []
    public_spec = load_public_spec(metadata)
    evaluation_spec = load_evaluation_spec(metadata)
    if public_spec is None:
        errors.append("compliant task must define metadata.public_spec")
        return errors
    if evaluation_spec is None:
        errors.append("compliant task must define metadata.evaluation_spec")
        return errors

    errors.extend(validate_public_spec_shape(public_spec))
    errors.extend(validate_evaluation_spec_shape(evaluation_spec))
    errors.extend(_validate_generated_task(task_dir, metadata, public_spec, task_markdown=task_markdown))
    errors.extend(_validate_workspace_task_premise(metadata))
    errors.extend(_validate_spec_hashes(metadata, public_spec))
    errors.extend(_validate_behavior_coverage(public_spec, evaluation_spec))
    errors.extend(_validate_api_coverage(public_spec, evaluation_spec))
    errors.extend(
        _validate_mapping_nodeids(
            task_dir,
            evaluation_spec,
            additional_test_nodeids=additional_test_nodeids,
        )
    )
    if not ignore_test_api_usage:
        errors.extend(
            _validate_test_api_usage(
                task_dir,
                public_spec,
                test_source_overrides=test_source_overrides,
            )
        )
    errors.extend(_validate_task_leakage(task_dir, metadata))
    return errors


def _legacy_warnings(metadata: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if isinstance(metadata.get("public_spec"), dict):
        warnings.append("metadata.public_spec present but spec_status is not compliant")
    return warnings


def _validate_generated_task(
    task_dir: Path,
    metadata: dict[str, Any],
    public_spec: dict[str, Any],
    *,
    task_markdown: str | None = None,
) -> list[str]:
    errors: list[str] = []
    expected = render_public_task(metadata)
    if task_markdown is None:
        task_path = task_dir / "TASK.md"
        if not task_path.is_file():
            errors.append("compliant task must include TASK.md generated from public_spec")
            return errors
        actual = task_path.read_text(encoding="utf-8")
    else:
        actual = task_markdown
    if actual != expected:
        errors.append("TASK.md does not match render(public_spec)")
    stored_hash = metadata.get("generated_task_hash")
    if isinstance(stored_hash, str) and stored_hash != compute_generated_task_hash(actual):
        errors.append("metadata.generated_task_hash does not match TASK.md")
    if public_spec and isinstance(metadata.get("spec_hash"), str):
        if metadata["spec_hash"] != compute_spec_hash(public_spec):
            errors.append("metadata.spec_hash does not match canonical public_spec hash")
    return errors


def _validate_workspace_task_premise(metadata: dict[str, Any]) -> list[str]:
    workspace_task = render_agent_workspace_task(metadata)
    errors: list[str] = []
    if COMPLETE_FEATURE_RESPONSIBILITY_MARKER not in workspace_task:
        errors.append("Agent workspace TASK is missing complete-feature responsibility marker")
    if COMPLETE_FEATURE_RESPONSIBILITY_HEADING not in workspace_task:
        errors.append("Agent workspace TASK is missing Complete Feature Responsibility")
    return errors


def _validate_spec_hashes(metadata: dict[str, Any], public_spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if metadata.get("spec_status") != SPEC_STATUS_COMPLIANT:
        errors.append("metadata.spec_status must be 'compliant'")
    if not isinstance(metadata.get("task_revision"), int):
        errors.append("metadata.task_revision must be an integer")
    expected = compute_spec_hash(public_spec)
    if metadata.get("spec_hash") != expected:
        errors.append("metadata.spec_hash mismatch")
    return errors


def _behavior_ids(public_spec: dict[str, Any]) -> set[str]:
    ids = {
        str(item.get("id"))
        for item in (public_spec.get("behaviors") or [])
        if isinstance(item, dict) and item.get("id")
    }
    isolation = public_spec.get("isolation_behavior")
    if isinstance(isolation, dict) and isolation.get("id"):
        ids.add(str(isolation["id"]))
    return ids


def _validate_behavior_coverage(
    public_spec: dict[str, Any],
    evaluation_spec: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    behavior_ids = _behavior_ids(public_spec)
    clause_ids = {
        str(item.get("behavior_id"))
        for item in (evaluation_spec.get("public_clauses") or [])
        if isinstance(item, dict) and item.get("behavior_id")
    }
    missing_clauses = sorted(behavior_ids - clause_ids)
    if missing_clauses:
        errors.append(
            "evaluation_spec.public_clauses missing behavior ids: "
            + ", ".join(missing_clauses)
        )

    hidden_covered: set[str] = set()
    for mapping in evaluation_spec.get("hidden_test_mappings") or []:
        if not isinstance(mapping, dict):
            continue
        hidden_covered.update(str(item) for item in (mapping.get("behavior_ids") or []))
    required_behaviors = {
        str(item.get("id"))
        for item in (public_spec.get("behaviors") or [])
        if isinstance(item, dict) and item.get("id")
    }
    missing_hidden = sorted(required_behaviors - hidden_covered)
    if missing_hidden:
        errors.append(
            "hidden tests do not cover required behaviors: " + ", ".join(missing_hidden)
        )

    for key in ("public_test_mappings", "hidden_test_mappings"):
        mappings = evaluation_spec.get(key) or []
        if not isinstance(mappings, list):
            continue
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            unknown = set(mapping.get("behavior_ids") or []) - behavior_ids
            if unknown:
                errors.append(
                    f"{key} references unknown behavior ids: {', '.join(sorted(unknown))}"
                )
            if not mapping.get("behavior_ids"):
                nodeid = mapping.get("nodeid", "<unknown>")
                errors.append(f"{key} entry must map to at least one behavior: {nodeid}")
    return errors


def _validate_api_coverage(
    public_spec: dict[str, Any],
    evaluation_spec: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    required_paths: set[str] = set()

    def collect(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for item in entries:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if isinstance(path, str):
                required_paths.add(path)
            collect(item.get("members"))

    collect(public_spec.get("required_api"))
    covered_paths = {
        str(item.get("path"))
        for item in (evaluation_spec.get("required_api_coverage") or [])
        if isinstance(item, dict) and item.get("path")
    }
    missing = sorted(required_paths - covered_paths)
    if missing:
        errors.append("required_api entries missing evaluation coverage: " + ", ".join(missing))
    extra = sorted(covered_paths - required_paths)
    if extra:
        errors.append("evaluation_spec.required_api_coverage has undeclared paths: " + ", ".join(extra))
    for item in evaluation_spec.get("required_api_coverage") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path", "<unknown>")
        for nodeid in item.get("covered_by_tests") or []:
            if not isinstance(nodeid, str) or not nodeid.startswith("hidden_tests/"):
                errors.append(
                    f"required API coverage for {path} must reference hidden test nodeids"
                )
    return errors


def _collect_test_nodeids(task_dir: Path, label: str) -> set[str]:
    nodeids: set[str] = set()
    test_dir = task_dir / label
    if not test_dir.is_dir():
        return nodeids
    for path in sorted(test_dir.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        relative = path.relative_to(task_dir).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                nodeids.add(f"{relative}::{node.name}")
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        nodeids.add(f"{relative}::{node.name}::{child.name}")
    return nodeids


def _validate_mapping_nodeids(
    task_dir: Path,
    evaluation_spec: dict[str, Any],
    *,
    additional_test_nodeids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    available = {
        "public_test_mappings": _collect_test_nodeids(task_dir, "public_tests"),
        "hidden_test_mappings": _collect_test_nodeids(task_dir, "hidden_tests"),
    }
    available["hidden_test_mappings"].update(additional_test_nodeids or set())
    for key, nodeids in available.items():
        for mapping in evaluation_spec.get(key) or []:
            if not isinstance(mapping, dict):
                continue
            nodeid = mapping.get("nodeid")
            if not isinstance(nodeid, str) or nodeid not in nodeids:
                errors.append(f"{key} references missing test nodeid: {nodeid}")
    hidden_nodeids = available["hidden_test_mappings"]
    for item in evaluation_spec.get("required_api_coverage") or []:
        if not isinstance(item, dict):
            continue
        for nodeid in item.get("covered_by_tests") or []:
            if not isinstance(nodeid, str) or nodeid not in hidden_nodeids:
                errors.append(
                    "required_api_coverage references missing hidden test nodeid: "
                    f"{nodeid}"
                )
    return errors


def _collect_declared_api_paths(public_spec: dict[str, Any]) -> set[str]:
    paths: set[str] = set()

    def walk(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if isinstance(path, str):
                paths.add(path)
            walk(entry.get("members"))

    walk(public_spec.get("required_api"))
    walk(public_spec.get("optional_api"))
    return paths


TEST_API_USAGE_FILENAME = "test_api_usage.json"
TEST_API_USAGE_SCHEMA = "featureliftbench.test_api_usage.v1"


def _collect_declared_api_kinds(public_spec: dict[str, Any]) -> dict[str, str]:
    kinds: dict[str, str] = {}

    def walk(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            kind = entry.get("kind")
            if isinstance(path, str) and isinstance(kind, str):
                kinds[path] = kind.strip().lower()
            walk(entry.get("members"))

    walk(public_spec.get("required_api"))
    walk(public_spec.get("optional_api"))
    return kinds


def _imported_root(expr: ast.AST, imported: dict[str, str]) -> str | None:
    """Resolve the imported featurelifted root used by an expression."""

    cur = expr
    while True:
        if isinstance(cur, ast.Name):
            imported_name = imported.get(cur.id)
            return f"featurelifted.{imported_name}" if imported_name else None
        if isinstance(cur, ast.Attribute):
            cur = cur.value
            continue
        if isinstance(cur, ast.Call):
            cur = cur.func
            continue
        if isinstance(cur, ast.Subscript):
            cur = cur.value
            continue
        return None


def _attribute_path(node: ast.Attribute, imported: dict[str, str]) -> str | None:
    """Resolve a call-free attribute path rooted at a featurelifted import."""

    attrs: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        attrs.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    if cur.id == "featurelifted":
        base = "featurelifted"
    elif cur.id in imported:
        base = f"featurelifted.{imported[cur.id]}"
    else:
        return None
    return base + "." + ".".join(reversed(attrs))


def _extract_test_api_refs(
    source: str,
    *,
    api_kinds: dict[str, str] | None = None,
) -> set[str]:
    """Best-effort AST extraction of featurelifted API refs (including call chains).

    This is a discovery aid, not the sole contract fact source. Prefer the
    explicit ``evaluation/test_api_usage.json`` manifest when present.
    """

    refs: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return refs

    imported: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "featurelifted":
            for alias in node.names:
                local = alias.asname or alias.name
                imported[local] = alias.name

    kinds = api_kinds or {}
    instance_kinds = {"class", "exception"}
    namespace_kinds = {"module", "class", "exception", "enum"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in imported:
            refs.add(f"featurelifted.{imported[node.id]}")
            continue
        if not isinstance(node, ast.Attribute):
            continue

        if isinstance(node.value, ast.Name):
            if node.value.id in imported:
                refs.add(f"featurelifted.{imported[node.value.id]}.{node.attr}")
            elif node.value.id == "featurelifted":
                refs.add(f"featurelifted.{node.attr}")
            continue

        if isinstance(node.value, ast.Call):
            base = _imported_root(node.value, imported)
            if base is not None and kinds.get(base) in instance_kinds:
                # Constructor/fluent chains retain the exported class owner.
                refs.add(f"{base}.{node.attr}")
            continue

        if isinstance(node.value, ast.Attribute):
            path = _attribute_path(node, imported)
            if path is None:
                continue
            parts = path.split(".")
            base = ".".join(parts[:2])
            parent = ".".join(parts[:-1])
            if kinds.get(base) == "module" or kinds.get(parent) in namespace_kinds:
                refs.add(path)

    for match in re.finditer(
        r"\bfeaturelifted\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)",
        source,
    ):
        refs.add(f"featurelifted.{match.group(1)}")
    return refs


def _load_test_api_usage_manifest(task_dir: Path) -> dict[str, Any] | None:
    path = task_dir / "evaluation" / TEST_API_USAGE_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {path.as_posix()}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()} must be a JSON object")
    return payload


def _api_ref_is_member_path(ref: str) -> bool:
    """True for ``featurelifted.Class.member`` (2+ dotted segments after package)."""

    parts = ref.removeprefix("featurelifted.").split(".")
    return len(parts) >= 2


def _validate_test_api_usage(
    task_dir: Path,
    public_spec: dict[str, Any],
    *,
    test_source_overrides: dict[str, str] | None = None,
) -> list[str]:
    """Validate public/hidden API usage against declared required/optional paths.

    Fact source priority:
    1. ``evaluation/test_api_usage.json`` manifest (``test_id -> api_ids``) when present
    2. AST extraction as a cross-check / fallback discovery signal

    Member paths (``featurelifted.X.y``) must be exactly declared. Declaring only
    the class root ``featurelifted.X`` does **not** authorize arbitrary members.
    """

    errors: list[str] = []
    declared = _collect_declared_api_paths(public_spec)
    api_kinds = _collect_declared_api_kinds(public_spec)
    declared_roots = {
        path.removeprefix("featurelifted.").split(".")[0]
        for path in declared
        if path.startswith("featurelifted.")
    }
    optional_paths: set[str] = set()

    def collect_optional(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if isinstance(path, str):
                optional_paths.add(path)
            collect_optional(entry.get("members"))

    collect_optional(public_spec.get("optional_api"))
    optional_roots = {
        path.removeprefix("featurelifted.").split(".")[0] for path in optional_paths
    }

    try:
        manifest = _load_test_api_usage_manifest(task_dir)
    except ValueError as exc:
        return [str(exc)]

    manifest_by_test: dict[str, set[str]] = {}
    manifest_by_file: dict[str, set[str]] = {}
    if manifest is not None:
        schema = str(manifest.get("schema_version") or "")
        if schema and schema != TEST_API_USAGE_SCHEMA:
            errors.append(
                f"evaluation/{TEST_API_USAGE_FILENAME} unsupported schema_version: {schema}"
            )
        tests = manifest.get("tests")
        if not isinstance(tests, list) or not tests:
            errors.append(
                f"evaluation/{TEST_API_USAGE_FILENAME} must define a non-empty tests list"
            )
        else:
            for item in tests:
                if not isinstance(item, dict):
                    errors.append(
                        f"evaluation/{TEST_API_USAGE_FILENAME} tests entries must be objects"
                    )
                    continue
                test_id = item.get("test_id")
                api_ids = item.get("api_ids")
                if not isinstance(test_id, str) or not test_id.strip():
                    errors.append(
                        f"evaluation/{TEST_API_USAGE_FILENAME} entry missing test_id"
                    )
                    continue
                if not isinstance(api_ids, list) or not all(
                    isinstance(x, str) and x.strip() for x in api_ids
                ):
                    errors.append(
                        f"evaluation/{TEST_API_USAGE_FILENAME} {test_id}: api_ids must be "
                        "a list of strings"
                    )
                    continue
                ids = {str(x).strip() for x in api_ids}
                manifest_by_test[test_id.strip()] = ids
                file_key = test_id.split("::", 1)[0]
                manifest_by_file.setdefault(file_key, set()).update(ids)
                for api_id in ids:
                    root = api_id.removeprefix("featurelifted.").split(".")[0]
                    if root in optional_roots or api_id in optional_paths:
                        errors.append(
                            f"evaluation/{TEST_API_USAGE_FILENAME} {test_id} lists "
                            f"optional API {api_id}"
                        )
                        continue
                    if api_id not in declared:
                        errors.append(
                            f"evaluation/{TEST_API_USAGE_FILENAME} {test_id} lists "
                            f"undeclared API {api_id}"
                        )

    overrides = test_source_overrides or {}
    for label in ("public_tests", "hidden_tests"):
        test_dir = task_dir / label
        sources: dict[str, str] = {}
        if test_dir.is_dir():
            for path in sorted(test_dir.rglob("*.py")):
                relative = path.relative_to(task_dir).as_posix()
                sources[relative] = path.read_text(encoding="utf-8")
        sources.update(
            {
                relative: source
                for relative, source in overrides.items()
                if relative.startswith(f"{label}/")
            }
        )
        for relative, source in sorted(sources.items()):
            refs = _extract_test_api_refs(source, api_kinds=api_kinds)
            file_manifest = manifest_by_file.get(relative, set())
            for ref in sorted(refs):
                if ref in STANDARD_MODULE_METADATA_REFS:
                    continue
                root = ref.removeprefix("featurelifted.").split(".")[0]
                if root in optional_roots or ref in optional_paths:
                    errors.append(
                        f"{relative} depends on optional API reference {ref}"
                    )
                    continue
                if ref not in declared:
                    # Member paths require exact declaration (no class-root loophole).
                    if _api_ref_is_member_path(ref) or root not in declared_roots:
                        errors.append(
                            f"{relative} uses undeclared API reference {ref}"
                        )
                if manifest is not None and file_manifest and ref not in file_manifest:
                    # Manifest is the audit fact source; AST-only extras are gaps.
                    if ref in declared or _api_ref_is_member_path(ref):
                        errors.append(
                            f"{relative} AST-discovered API {ref} missing from "
                            f"evaluation/{TEST_API_USAGE_FILENAME} for this file"
                        )
    return errors


def _validate_task_leakage(task_dir: Path, metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    task_path = task_dir / "TASK.md"
    if not task_path.is_file():
        return errors
    text = task_path.read_text(encoding="utf-8").lower()
    for token in ("hidden_tests/", "evaluation_spec", "oracle_manifest"):
        if token in text:
            errors.append(f"TASK.md must not mention private evaluator asset: {token}")
    evaluation_spec = load_evaluation_spec(metadata)
    if isinstance(evaluation_spec, dict):
        serialized = json.dumps(evaluation_spec, ensure_ascii=False)
        if serialized in task_path.read_text(encoding="utf-8"):
            errors.append("TASK.md leaks evaluation_spec content")
    for key in PRIVATE_METADATA_KEYS:
        if key in task_path.read_text(encoding="utf-8"):
            errors.append(f"TASK.md must not mention private metadata key: {key}")
    return errors
