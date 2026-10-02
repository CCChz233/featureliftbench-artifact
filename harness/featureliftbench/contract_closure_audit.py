"""Machine-readable contract-closure audit support for Python benchmark tasks."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .constitution_validate import (
    _collect_declared_api_kinds,
    _collect_declared_api_paths,
    _extract_test_api_refs,
)
from .metadata import load_metadata
from .validate import validate_task, validate_runnable_task


AUDIT_SCHEMA = "featureliftbench.contract_closure_machine_audit.v1"
REVIEW_SCHEMA = "featureliftbench.contract_closure_review.v1"
FINAL_VERDICTS = {"closed", "underspecified", "contradictory", "exclude"}
COMPONENT_VERDICTS = FINAL_VERDICTS | {"not_applicable"}


@dataclass(frozen=True)
class TestFunction:
    nodeid: str
    source: str
    line: int
    import_context: str = ""


def _test_functions(task_dir: Path, directory: str) -> list[TestFunction]:
    result: list[TestFunction] = []
    root = task_dir / directory
    if not root.is_dir():
        return result
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        relative = path.relative_to(task_dir).as_posix()
        import_context = "\n".join(
            segment
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            if (segment := ast.get_source_segment(text, node))
        )
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                source = ast.get_source_segment(text, node) or node.name
                result.append(
                    TestFunction(f"{relative}::{node.name}", source, node.lineno, import_context)
                )
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        source = ast.get_source_segment(text, child) or child.name
                        result.append(
                            TestFunction(
                                f"{relative}::{node.name}::{child.name}",
                                source,
                                child.lineno,
                                import_context,
                            )
                        )
    return result


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _assertions(source: str, *, start_line: int) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()

    def add(kind: str, node: ast.AST, expression: str) -> None:
        line = start_line + int(getattr(node, "lineno", 1)) - 1
        key = (kind, line, expression)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "assertion_id": f"A{len(rows) + 1:03d}",
                "kind": kind,
                "line": line,
                "expression": expression,
            }
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            add("assert", node, ast.unparse(node.test))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                if not isinstance(call, ast.Call):
                    continue
                name = _call_name(call.func)
                if name.endswith("pytest.raises") or name == "raises":
                    add("raises", call, ast.unparse(call))
                elif name.endswith("pytest.warns") or name == "warns":
                    add("warns", call, ast.unparse(call))
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"pytest.fail", "fail"}:
                add("explicit_fail", node, ast.unparse(node))
    return rows


def _risk_tags(test: TestFunction, assertions: list[dict[str, Any]]) -> list[str]:
    source = test.source.lower()
    expressions = "\n".join(str(item["expression"]).lower() for item in assertions)
    tags: set[str] = set()
    if "pytest.raises" in source or " raises(" in source:
        tags.add("exception_semantics")
    if "match=" in source or "str(" in expressions and "==" in expressions:
        tags.add("exact_error_text")
    if any(token in source for token in ("monkeypatch", "os.environ", "getenv(", "setenv(")):
        tags.add("environment_state")
    if any(token in source for token in ("tmp_path", "tmpdir", "path(", "open(")):
        tags.add("filesystem_resource")
    if any(token in source for token in ("time.", "datetime.now", "random.", "sleep(")):
        tags.add("time_or_randomness")
    if any(token in test.nodeid.lower() for token in ("order", "priority", "sequence", "sorted")):
        tags.add("ordering_semantics")
    if any(token in test.nodeid.lower() for token in ("reset", "mutat", "update", "state", "cache")):
        tags.add("state_mutation")
    if not assertions:
        tags.add("implicit_no_exception_assertion")
    return sorted(tags)


def _mapping_by_nodeid(metadata: dict[str, Any], key: str) -> dict[str, list[str]]:
    evaluation = metadata.get("evaluation_spec")
    if not isinstance(evaluation, dict):
        return {}
    result: dict[str, list[str]] = {}
    for item in evaluation.get(key) or []:
        if not isinstance(item, dict) or not isinstance(item.get("nodeid"), str):
            continue
        result[str(item["nodeid"])] = sorted({str(value) for value in item.get("behavior_ids") or []})
    return result


def _private_contract(task_dir: Path) -> dict[str, Any]:
    path = task_dir / "evaluation" / "behavior_contract.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _private_mapping_by_nodeid(contract: dict[str, Any], key: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in contract.get(key) or []:
        if not isinstance(item, dict) or not isinstance(item.get("nodeid"), str):
            continue
        ids = item.get("public_clause_ids")
        if ids is None:
            ids = item.get("behavior_ids")
        result[str(item["nodeid"])] = sorted({str(value) for value in ids or []})
    return result


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def audit_task(task_dir: str | Path, *, release_group: str, lift_type: str | None = None,
               primary_coupling: str | None = None) -> dict[str, Any]:
    root = Path(task_dir)
    metadata = load_metadata(root).data
    public_spec = metadata.get("public_spec") if isinstance(metadata.get("public_spec"), dict) else {}
    declared_paths = _collect_declared_api_paths(public_spec)
    api_kinds = _collect_declared_api_kinds(public_spec)
    strict = validate_task(root)
    runnable = validate_runnable_task(root)
    contract = _private_contract(root)
    public_mappings = _mapping_by_nodeid(metadata, "public_test_mappings")
    hidden_mappings = _mapping_by_nodeid(metadata, "hidden_test_mappings")
    private_public = _private_mapping_by_nodeid(contract, "public_test_mappings")
    private_hidden = _private_mapping_by_nodeid(contract, "hidden_test_mappings")
    tests: list[dict[str, Any]] = []
    mapping_issues: list[str] = []

    for directory, mappings, private_mappings in (
        ("public_tests", public_mappings, private_public),
        ("hidden_tests", hidden_mappings, private_hidden),
    ):
        for test in _test_functions(root, directory):
            assertions = _assertions(test.source, start_line=test.line)
            analysis_source = f"{test.import_context}\n{test.source}"
            refs = sorted(_extract_test_api_refs(analysis_source, api_kinds=api_kinds))
            behavior_ids = mappings.get(test.nodeid, [])
            private_ids = private_mappings.get(test.nodeid, [])
            if not behavior_ids:
                mapping_issues.append(f"{test.nodeid}: missing metadata behavior mapping")
            if not private_ids:
                mapping_issues.append(f"{test.nodeid}: missing private behavior mapping")
            if behavior_ids != private_ids:
                mapping_issues.append(
                    f"{test.nodeid}: metadata/private mapping mismatch "
                    f"{behavior_ids!r} != {private_ids!r}"
                )
            tests.append(
                {
                    "nodeid": test.nodeid,
                    "visibility": "public" if directory == "public_tests" else "hidden",
                    "behavior_ids": behavior_ids,
                    "private_behavior_ids": private_ids,
                    "api_ids": refs,
                    "undeclared_api_ids": sorted(set(refs) - declared_paths),
                    "assertions": assertions,
                    "risk_tags": _risk_tags(test, assertions),
                    "source_sha256": hashlib.sha256(test.source.encode("utf-8")).hexdigest(),
                }
            )

    expected_public = {item.nodeid for item in _test_functions(root, "public_tests")}
    expected_hidden = {item.nodeid for item in _test_functions(root, "hidden_tests")}
    for nodeid in sorted(set(public_mappings) - expected_public):
        mapping_issues.append(f"{nodeid}: stale metadata public mapping")
    for nodeid in sorted(set(hidden_mappings) - expected_hidden):
        mapping_issues.append(f"{nodeid}: stale metadata hidden mapping")

    task_path = root / "TASK.md"
    contract_hash = contract.get("spec_sha256")
    actual_hash = _sha256(task_path)
    contract_issues: list[str] = []
    if not contract:
        contract_issues.append("missing or invalid evaluation/behavior_contract.json")
    if contract.get("task_id") != root.name:
        contract_issues.append("behavior contract task_id mismatch")
    if contract_hash != actual_hash:
        contract_issues.append("behavior contract spec_sha256 mismatch")
    if contract.get("schema_version") != "featureliftbench.behavior_contract.v1":
        contract_issues.append("behavior contract schema_version missing or unsupported")
    if contract.get("review_status") not in {
        "ai_assisted_reviewed", "author_reviewed", "double_reviewed", "adjudicated"
    }:
        contract_issues.append("behavior contract lacks a completed review_status")

    return {
        "task_id": root.name,
        "task_path": root.as_posix(),
        "release_group": release_group,
        "lift_type": lift_type,
        "primary_coupling": primary_coupling,
        "task_revision": metadata.get("task_revision"),
        "spec_hash": metadata.get("spec_hash"),
        "generated_task_hash": metadata.get("generated_task_hash"),
        "strict_validation": {
            "valid": strict.valid,
            "errors": strict.errors,
            "warnings": strict.warnings,
        },
        "runnable_validation": {
            "valid": runnable.valid,
            "errors": runnable.errors,
            "warnings": runnable.warnings,
        },
        "declared_api_count": len(declared_paths),
        "test_count": len(tests),
        "assertion_count": sum(len(item["assertions"]) for item in tests),
        "undeclared_api_ids": sorted(
            {api_id for item in tests for api_id in item["undeclared_api_ids"]}
        ),
        "mapping_issues": sorted(set(mapping_issues)),
        "behavior_contract_issues": sorted(set(contract_issues)),
        "tests": tests,
    }


def review_template(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": REVIEW_SCHEMA,
        "task_id": task["task_id"],
        "review_status": "pending",
        "reviewer": None,
        "reviewed_at": None,
        "oracle_relation": "pending",
        "components": {
            "api_surface": {"verdict": "pending", "evidence": [], "issues": []},
            "behavior": {"verdict": "pending", "evidence": [], "issues": []},
            "dependency_environment": {"verdict": "pending", "evidence": [], "issues": []},
        },
        "tests": [
            {
                "nodeid": test["nodeid"],
                "behavior_ids": test["behavior_ids"],
                "verdict": "pending",
                "evidence_basis": [],
                "notes": "",
            }
            for test in task["tests"]
        ],
        "overall_verdict": "pending",
        "revision_required": None,
        "issues": [],
        "notes": "",
    }


def validate_review(review: dict[str, Any], task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if review.get("schema_version") != REVIEW_SCHEMA:
        errors.append("unsupported review schema_version")
    if review.get("task_id") != task.get("task_id"):
        errors.append("review task_id mismatch")
    if review.get("review_status") not in {"ai_assisted_reviewed", "human_reviewed", "double_reviewed", "adjudicated"}:
        errors.append("review_status is not complete")
    if not review.get("reviewer") or not review.get("reviewed_at"):
        errors.append("reviewer and reviewed_at are required")
    if review.get("oracle_relation") not in {
        "direct_oracle", "specified_adapter", "inferred_adapter", "no_upstream_oracle"
    }:
        errors.append("oracle_relation is missing or invalid")
    components = review.get("components")
    if not isinstance(components, dict):
        errors.append("components must be an object")
    else:
        for name in ("api_surface", "behavior", "dependency_environment"):
            value = components.get(name)
            if not isinstance(value, dict) or value.get("verdict") not in COMPONENT_VERDICTS:
                errors.append(f"components.{name} lacks a final verdict")
    expected = {item["nodeid"] for item in task.get("tests") or []}
    actual: set[str] = set()
    for item in review.get("tests") or []:
        if not isinstance(item, dict) or not isinstance(item.get("nodeid"), str):
            errors.append("review tests entries must be objects with nodeid")
            continue
        nodeid = str(item["nodeid"])
        if nodeid in actual:
            errors.append(f"duplicate reviewed test: {nodeid}")
        actual.add(nodeid)
        if item.get("verdict") not in FINAL_VERDICTS:
            errors.append(f"{nodeid}: verdict is not final")
        evidence = item.get("evidence_basis")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{nodeid}: evidence_basis is required")
    for nodeid in sorted(expected - actual):
        errors.append(f"missing reviewed test: {nodeid}")
    for nodeid in sorted(actual - expected):
        errors.append(f"stale reviewed test: {nodeid}")
    if review.get("overall_verdict") not in FINAL_VERDICTS:
        errors.append("overall_verdict is not final")
    if not isinstance(review.get("revision_required"), bool):
        errors.append("revision_required must be boolean")
    return errors


def write_summary_csv(path: Path, tasks: Iterable[dict[str, Any]]) -> None:
    fields = [
        "task_id", "release_group", "lift_type", "primary_coupling", "test_count",
        "assertion_count", "strict_valid", "strict_error_count", "undeclared_api_count",
        "mapping_issue_count", "behavior_contract_issue_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for task in tasks:
            writer.writerow(
                {
                    "task_id": task["task_id"],
                    "release_group": task["release_group"],
                    "lift_type": task.get("lift_type") or "",
                    "primary_coupling": task.get("primary_coupling") or "",
                    "test_count": task["test_count"],
                    "assertion_count": task["assertion_count"],
                    "strict_valid": task["strict_validation"]["valid"],
                    "strict_error_count": len(task["strict_validation"]["errors"]),
                    "undeclared_api_count": len(task["undeclared_api_ids"]),
                    "mapping_issue_count": len(task["mapping_issues"]),
                    "behavior_contract_issue_count": len(task["behavior_contract_issues"]),
                }
            )
