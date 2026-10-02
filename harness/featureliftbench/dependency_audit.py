"""Audit helpers for task dependency lock consistency."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .dependency_install import (
    allowed_dependency_names,
    dependency_lock_path,
    dependency_names_from_lock,
    vendor_wheel_present,
)
from .metrics import dependency_name


@dataclass
class TaskDependencyIssue:
    task_id: str
    kind: str
    message: str


@dataclass
class TaskDependencyAudit:
    task_id: str
    task_dir: Path
    allowed: list[str] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)
    issues: list[TaskDependencyIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def normalized_allowed_set(metadata: dict[str, Any]) -> set[str]:
    return {dependency_alias(name) for name in allowed_dependency_names(metadata)}


def normalized_lock_set(task_dir: Path, metadata: dict[str, Any]) -> set[str]:
    lock_path = dependency_lock_path(task_dir, metadata)
    if lock_path is None or not lock_path.is_file():
        return set()
    return set(dependency_names_from_lock(lock_path))


def validate_lock_allowed_consistency(metadata: dict[str, Any], task_dir: Path) -> list[str]:
    """Return validation errors when allowed_dependencies and requirements.lock disagree."""

    if metadata.get("language") == "go":
        return []

    allowed = normalized_allowed_set(metadata)
    locked = normalized_lock_set(task_dir, metadata)
    errors: list[str] = []

    if allowed and not locked:
        errors.append(
            "allowed_dependencies is non-empty but requirements.lock is empty; "
            "pin every allowed dependency in requirements.lock"
        )
    elif not allowed and locked:
        errors.append(
            "requirements.lock lists dependencies but allowed_dependencies is empty: "
            + ", ".join(sorted(locked))
        )
    elif allowed != locked:
        missing_in_lock = sorted(allowed - locked)
        extra_in_lock = sorted(locked - allowed)
        parts: list[str] = []
        if missing_in_lock:
            parts.append("missing from lock: " + ", ".join(missing_in_lock))
        if extra_in_lock:
            parts.append("extra in lock: " + ", ".join(extra_in_lock))
        errors.append(
            "allowed_dependencies and requirements.lock must match: " + "; ".join(parts)
        )

    return errors


def parse_oracle_runtime_dependencies(manifest_path: Path) -> list[str]:
    if not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw = payload.get("runtime_dependencies")
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        token = item.strip().split()[0] if item.strip() else ""
        if not token or token.lower() in {"via", "empty"}:
            continue
        name = dependency_name(token)
        if name:
            names.append(name)
    return names


def audit_task_dependencies(
    task_dir: Path,
    *,
    check_wheels: bool = True,
    check_oracle_manifest: bool = True,
) -> TaskDependencyAudit:
    task_dir = task_dir.resolve()
    task_id = task_dir.name
    metadata_path = task_dir / "metadata.json"
    audit = TaskDependencyAudit(task_id=task_id, task_dir=task_dir)

    if not metadata_path.is_file():
        audit.issues.append(
            TaskDependencyIssue(task_id, "missing_metadata", "metadata.json not found")
        )
        return audit

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        audit.issues.append(
            TaskDependencyIssue(task_id, "invalid_metadata", f"metadata.json is invalid JSON: {exc}")
        )
        return audit

    if metadata.get("language") == "go":
        return audit

    audit.allowed = sorted(normalized_allowed_set(metadata))
    audit.locked = sorted(normalized_lock_set(task_dir, metadata))

    for message in validate_lock_allowed_consistency(metadata, task_dir):
        audit.issues.append(TaskDependencyIssue(task_id, "allowed_vs_lock_mismatch", message))

    if check_wheels:
        for package in audit.locked:
            if not vendor_wheel_present(package):
                audit.issues.append(
                    TaskDependencyIssue(
                        task_id,
                        "lock_package_missing_wheel",
                        f"requirements.lock dependency missing vendor wheel: {package}",
                    )
                )

    if check_oracle_manifest:
        manifest_path = task_dir / "evaluation" / "oracle_manifest.json"
        oracle_deps = parse_oracle_runtime_dependencies(manifest_path)
        locked_set = set(audit.locked)
        for package in oracle_deps:
            if package not in locked_set:
                audit.issues.append(
                    TaskDependencyIssue(
                        task_id,
                        "oracle_runtime_dep_not_in_lock",
                        f"oracle_manifest runtime dependency not pinned in lock: {package}",
                    )
                )

    return audit


def list_task_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "metadata.json").is_file()
    )


def audit_task_root(
    root: Path,
    *,
    check_wheels: bool = True,
    check_oracle_manifest: bool = True,
) -> list[TaskDependencyAudit]:
    return [
        audit_task_dependencies(
            task_dir,
            check_wheels=check_wheels,
            check_oracle_manifest=check_oracle_manifest,
        )
        for task_dir in list_task_dirs(root)
    ]


from .benchmark_wheels import load_benchmark_wheel_aliases


def dependency_alias(name: str) -> str:
    """Map legacy allowed names to PyPI distribution names."""

    normalized = dependency_name(name)
    aliases = load_benchmark_wheel_aliases()
    return aliases.get(normalized, normalized)


def lock_lines_for_allowed(
    allowed: list[str],
    pin_specs: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    for item in allowed:
        if not isinstance(item, str):
            continue
        package = dependency_alias(item)
        spec = pin_specs.get(package)
        if spec:
            lines.append(spec)
        elif "==" in item or ">=" in item or item.startswith(item.split("==")[0]):
            lines.append(item if "==" in item or ">=" in item else f"{package}=={item}")
    return sorted(set(lines), key=str.lower)
