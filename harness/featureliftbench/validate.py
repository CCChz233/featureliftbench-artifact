"""Task directory validation."""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .constitution_validate import validate_constitution
from .dependency_audit import validate_lock_allowed_consistency
from .closure_gold import load_closure_gold
from .metadata import MetadataError, load_metadata, validate_metadata_shape
from .task_spec import SPEC_STATUS_COMPLIANT, get_spec_status


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating one task directory."""

    task_dir: Path
    task_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


PYTHON_REQUIRED_PATHS = (
    "metadata.json",
    "requirements.lock",
    "repo",
    "public_tests",
    "hidden_tests",
    "evaluation",
    "evaluation/forbidden_imports.txt",
    "evaluation/oracle_manifest.json",
)

GO_REQUIRED_PATHS = (
    "metadata.json",
    "repo",
    "public_tests",
    "hidden_tests",
    "evaluation",
    "evaluation/forbidden_imports.txt",
    "environment",
    "environment/go.mod",
)


def validate_task(task_dir: str | Path) -> ValidationResult:
    """Validate a benchmark task directory."""

    root = Path(task_dir)
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists():
        return ValidationResult(task_dir=root, task_id="", errors=[f"task dir not found: {root}"])
    if not root.is_dir():
        return ValidationResult(task_dir=root, task_id="", errors=[f"task path is not a directory: {root}"])

    metadata = None
    language = "python"
    try:
        metadata = load_metadata(root)
        language = str(metadata.data.get("language", "python"))
    except MetadataError as exc:
        errors.append(str(exc))

    required_paths = GO_REQUIRED_PATHS if language == "go" else PYTHON_REQUIRED_PATHS
    for relative_path in required_paths:
        path = root / relative_path
        if not path.exists():
            errors.append(f"missing required path: {relative_path}")

    task_id = ""
    if metadata is not None:
        task_id = metadata.task_id
        errors.extend(validate_metadata_shape(metadata.data))

        if task_id and task_id != root.name:
            errors.append(f"task_id must match directory name: {task_id} != {root.name}")

        if language == "go":
            errors.extend(_validate_go_tests(root))
            errors.extend(_validate_go_environment(metadata.data, root))
        else:
            errors.extend(_validate_dependency_sets(metadata.data))
            errors.extend(_validate_lock_file_name(metadata.data, root))
            errors.extend(validate_lock_allowed_consistency(metadata.data, root))

    if language != "go":
        oracle_manifest = root / "evaluation" / "oracle_manifest.json"
        if oracle_manifest.exists():
            try:
                json.loads(oracle_manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON: evaluation/oracle_manifest.json: {exc}")
            except OSError as exc:
                errors.append(f"cannot read evaluation/oracle_manifest.json: {exc}")
        closure_path = root / "evaluation" / "closure_gold.json"
        if closure_path.exists():
            closure = load_closure_gold(root, allow_legacy=False)
            errors.extend(
                f"invalid closure gold: {message}" for message in closure.errors
            )
        behavior_path = root / "evaluation" / "behavior_contract.json"
        if behavior_path.exists():
            errors.extend(_validate_behavior_contract(root, behavior_path))

    if metadata is not None and get_spec_status(metadata.data) == SPEC_STATUS_COMPLIANT:
        errors.extend(validate_constitution(root, metadata.data))
    elif metadata is not None and isinstance(metadata.data.get("public_spec"), dict):
        warnings.append("metadata.public_spec present but spec_status is not compliant")

    return ValidationResult(task_dir=root, task_id=task_id, errors=errors, warnings=warnings)


def validate_runnable_task(task_dir: str | Path) -> ValidationResult:
    """Validate a task while preserving a cryptographically frozen legacy contract."""

    result = validate_task(task_dir)
    if result.valid or not result.task_id:
        return result
    compatibility_errors = [
        error
        for error in result.errors
        if " uses undeclared API reference featurelifted." in error
    ]
    if len(compatibility_errors) != len(result.errors):
        return result

    from .benchmark_freeze import benchmark_freeze_provenance

    provenance = benchmark_freeze_provenance(result.task_id)
    if provenance is None:
        return result
    try:
        metadata = load_metadata(Path(task_dir)).data
    except MetadataError:
        return result
    if (
        provenance.get("spec_hash") != metadata.get("spec_hash")
        or provenance.get("generated_task_hash") != metadata.get("generated_task_hash")
    ):
        return result
    return ValidationResult(
        task_dir=result.task_dir,
        task_id=result.task_id,
        errors=[],
        warnings=result.warnings
        + [
            "active benchmark freeze preserves legacy implicit API references: "
            f"{len(compatibility_errors)}"
        ],
    )


def _validate_behavior_contract(root: Path, path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid JSON: evaluation/behavior_contract.json: {exc}"]
    if not isinstance(payload, dict):
        return ["evaluation/behavior_contract.json must be a JSON object"]
    if payload.get("task_id") != root.name:
        errors.append("behavior contract task_id must match directory name")
    clauses = payload.get("public_clauses")
    clause_ids = {
        str(item.get("behavior_id"))
        for item in clauses or []
        if isinstance(item, dict) and item.get("behavior_id")
    }
    if not clause_ids:
        errors.append("behavior contract must contain public clauses")
    for key in ("public_test_mappings", "hidden_test_mappings"):
        mappings = payload.get(key)
        if not isinstance(mappings, list):
            errors.append(f"behavior contract {key} must be a list")
            continue
        for item in mappings:
            if not isinstance(item, dict):
                errors.append(f"behavior contract {key} entries must be objects")
                continue
            unknown = set(item.get("public_clause_ids") or []) - clause_ids
            if unknown:
                errors.append(
                    f"behavior contract {key} references unknown clauses: {', '.join(sorted(unknown))}"
                )
    task_path = root / "TASK.md"
    expected_hash = payload.get("spec_sha256")
    if task_path.is_file() and isinstance(expected_hash, str):
        actual = hashlib.sha256(task_path.read_bytes()).hexdigest()
        if actual != expected_hash:
            errors.append("behavior contract spec_sha256 does not match TASK.md")
    return errors


def _validate_go_tests(root: Path) -> list[str]:
    errors: list[str] = []
    for label, rel in (("public", "public_tests"), ("hidden", "hidden_tests")):
        test_dir = root / rel
        if not test_dir.is_dir():
            continue
        go_tests = list(test_dir.glob("*_test.go"))
        if not go_tests:
            errors.append(f"{label} tests must include at least one *_test.go file under {rel}/")
    return errors


def _validate_go_environment(metadata: dict, task_dir: Path) -> list[str]:
    errors: list[str] = []
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []

    go_mod = task_dir / "environment" / "go.mod"
    if go_mod.is_file():
        text = go_mod.read_text(encoding="utf-8")
        if "module " not in text:
            errors.append("environment/go.mod must declare a module path")

    cgo = environment.get("cgo_enabled", False)
    if cgo is True:
        errors.append("Go tasks must set environment.cgo_enabled to false for pilot track")

    for metadata_key, filename in (
        ("allowed_modules", "allowed_modules.txt"),
        ("forbidden_modules", "forbidden_modules.txt"),
    ):
        if isinstance(environment.get(metadata_key), list):
            relative_path = f"evaluation/{filename}"
            if not (task_dir / relative_path).is_file():
                errors.append(f"missing required path: {relative_path}")

    return errors


def _validate_dependency_sets(metadata: dict) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []

    allowed = environment.get("allowed_dependencies", [])
    forbidden = environment.get("forbidden_dependencies", [])
    if not isinstance(allowed, list) or not isinstance(forbidden, list):
        return []

    allowed_names = {_normalize_distribution_name(item) for item in allowed if isinstance(item, str)}
    forbidden_names = {_normalize_distribution_name(item) for item in forbidden if isinstance(item, str)}
    conflicts = sorted(allowed_names & forbidden_names)
    if not conflicts:
        return []

    return [f"dependencies cannot be both allowed and forbidden: {', '.join(conflicts)}"]


def _validate_lock_file_name(metadata: dict, task_dir: Path) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []

    lock_file = environment.get("dependency_lock")
    if not isinstance(lock_file, str):
        return []

    if Path(lock_file).is_absolute() or ".." in Path(lock_file).parts:
        return ["environment.dependency_lock must be a relative file inside the task directory"]

    if not (task_dir / lock_file).exists():
        return [f"dependency lock file not found: {lock_file}"]

    return []


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
