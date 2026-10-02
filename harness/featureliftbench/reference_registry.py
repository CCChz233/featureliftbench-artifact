"""Frozen, code-free compactness reference measurements."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REFERENCE_REGISTRY_ENV = "FEATURELIFTBENCH_REFERENCE_REGISTRY"
DEFAULT_REFERENCE_REGISTRY = Path("benchmark/references/compactness.json")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def reference_registry_path() -> Path:
    configured = os.environ.get(REFERENCE_REGISTRY_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (project_root() / DEFAULT_REFERENCE_REGISTRY).resolve()


def compactness_reference(task_id: str) -> dict[str, Any] | None:
    path = reference_registry_path()
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = payload.get("tasks") if isinstance(payload, dict) else None
    record = tasks.get(task_id) if isinstance(tasks, dict) else None
    return record if isinstance(record, dict) else None
