"""Frozen source materialization for the Pruned-Context ablation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT
from .source_archive import tree_stats


PRUNED_POLICY_ID = "featureliftbench.pruned_context.v1"
DEFAULT_PRUNED_REGISTRY = REPO_ROOT / "benchmark" / "sources" / "pruned_registry.json"


def load_pruned_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path or DEFAULT_PRUNED_REGISTRY).resolve()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if payload.get("policy_id") != PRUNED_POLICY_ID:
        raise ValueError(
            f"unexpected pruned registry policy: {payload.get('policy_id')!r}"
        )
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        raise ValueError("pruned registry tasks must be an object")
    return payload


def materialize_pruned_task_source(
    task_id: str,
    destination: str | Path,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Copy the frozen task-local snapshot after verifying its tree digest."""

    registry = load_pruned_registry(registry_path)
    raw = registry["tasks"].get(task_id)
    if not isinstance(raw, dict):
        raise ValueError(f"{task_id}: missing from frozen pruned registry")
    relative = str(raw.get("source_path") or "")
    source = (REPO_ROOT / relative).resolve()
    task_root = (REPO_ROOT / "benchmark" / "tasks").resolve()
    try:
        source.relative_to(task_root)
    except ValueError as exc:
        raise ValueError(f"{task_id}: pruned source escapes benchmark/tasks") from exc
    if not source.is_dir():
        raise ValueError(f"{task_id}: frozen pruned source is missing: {relative}")
    actual = tree_stats(source)
    expected = str(raw.get("source_tree_sha256") or "")
    if actual.source_tree_sha256 != expected:
        raise ValueError(
            f"{task_id}: pruned source digest mismatch "
            f"(expected {expected}, got {actual.source_tree_sha256})"
        )

    target = Path(destination).resolve()
    if target.exists():
        raise ValueError(f"pruned materialization destination already exists: {target}")
    shutil.copytree(source, target, symlinks=True)
    return {
        "policy_id": registry.get("policy_id"),
        "registry_freeze_id": registry.get("freeze_id"),
        "source_snapshot_id": raw.get("source_snapshot_id"),
        "source_digest": expected,
        "snapshot_scope": "pruned_context_v1",
        "tracked_file_count": actual.tracked_file_count,
        "python_file_count": actual.python_file_count,
        "python_loc": actual.python_loc,
        "status": "verified",
    }


def pruned_source_provenance(
    task_id: str,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return frozen pruned provenance without materializing a workspace."""

    registry = load_pruned_registry(registry_path)
    raw = registry["tasks"].get(task_id)
    if not isinstance(raw, dict):
        raise ValueError(f"{task_id}: missing from frozen pruned registry")
    return {
        "policy_id": registry.get("policy_id"),
        "registry_freeze_id": registry.get("freeze_id"),
        "source_snapshot_id": raw.get("source_snapshot_id"),
        "source_digest": raw.get("source_tree_sha256"),
        "snapshot_scope": "pruned_context_v1",
        "status": "frozen",
    }
