"""Materialize frozen Full-Repository sources without using the agent's final repo."""

from __future__ import annotations

import json
from pathlib import Path

from featureliftbench.source_archive import materialize_snapshot, source_indexes, load_source_registry


def materialize_frozen_repo(root: Path, task_id: str, cache_dir: Path) -> Path:
    registry = load_source_registry(root / "benchmark" / "sources" / "registry.json")
    _snapshots, by_task = source_indexes(registry)
    snapshot = by_task.get(task_id)
    if snapshot is None:
        raise FileNotFoundError(f"{task_id}: no frozen source snapshot")
    snapshot_id = str(snapshot.get("source_snapshot_id") or task_id)
    dest = cache_dir / snapshot_id
    marker = dest / ".flb-source-ready.json"
    if marker.is_file() and dest.is_dir() and any(dest.iterdir()):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    materialize_snapshot(snapshot, dest, root=root)
    marker.write_text(json.dumps({"task_id": task_id, "source_snapshot_id": snapshot_id}, indent=2), encoding="utf-8")
    return dest
