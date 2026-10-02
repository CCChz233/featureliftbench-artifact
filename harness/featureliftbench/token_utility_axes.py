"""Task axes for token-utility stratification.

Lift type is the scientific task axis (Direct / Adapted / Composite).
Difficulty uses construction proxies only: Python-150, hard3, External-50.
``metadata.difficulty`` is not a scientific easy/medium/hard label.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LIFT_TYPES = ("Direct", "Adapted", "Composite")
COHORTS = ("python150", "hard3", "external50")
DEFAULT_AUDIT = ROOT / "reports/contract_closure_200/machine_audit.json"
DEFAULT_EXPANSION = ROOT / "benchmark/selection/external50_expansion_20260731.json"
DEFAULT_TASKS_ROOT = ROOT / "benchmark/python200_tasks"


def load_lift_types(
    *,
    audit_path: Path | None = None,
    expansion_path: Path | None = None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    expansion = json.loads((expansion_path or DEFAULT_EXPANSION).read_text(encoding="utf-8"))
    for row in expansion.get("rows") or []:
        if not isinstance(row, dict) or row.get("disposition") != "selected":
            continue
        lift = str(row.get("final_lift_type") or row.get("lift_type") or "")
        if lift in LIFT_TYPES:
            out[str(row["task_id"])] = lift
    audit = json.loads((audit_path or DEFAULT_AUDIT).read_text(encoding="utf-8"))
    for row in audit.get("tasks") or []:
        lift = str(row.get("lift_type") or "")
        if lift in LIFT_TYPES:
            out[str(row["task_id"])] = lift
    return out


def cohort_of(task_id: str, tags: list[str] | None = None) -> str:
    tags_l = {str(tag).lower() for tag in (tags or [])}
    if "__hard3_" in task_id or "batch-3" in tags_l:
        return "hard3"
    if "external50" in tags_l:
        return "external50"
    return "python150"


def load_task_axes(
    task_id: str,
    *,
    tasks_root: Path | None = None,
    lift_types: dict[str, str] | None = None,
) -> dict[str, Any]:
    lifts = lift_types if lift_types is not None else load_lift_types()
    meta_path = (tasks_root or DEFAULT_TASKS_ROOT) / task_id / "metadata.json"
    tags: list[str] = []
    entanglement_level = None
    metadata_difficulty = None
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        tags = [str(tag) for tag in (meta.get("tags") or [])]
        entanglement = meta.get("entanglement") if isinstance(meta.get("entanglement"), dict) else {}
        entanglement_level = entanglement.get("level")
        metadata_difficulty = meta.get("difficulty")
        if task_id not in lifts:
            for tag in tags:
                low = tag.lower()
                if low in {"direct", "adapted", "composite"}:
                    lifts[task_id] = low.capitalize()
                    break
    return {
        "task_id": task_id,
        "lift_type": lifts.get(task_id),
        "cohort": cohort_of(task_id, tags),
        "entanglement_level": entanglement_level,
        "metadata_difficulty": metadata_difficulty,
        "tags": tags,
    }


def model_label(suite: str) -> str:
    name = Path(suite).name
    text = f"{suite} {name}".lower()
    if "deepseek-v4-flash" in text and "python200" in name:
        return "flash_local_main200"
    if "deepseek-v4-flash" in text and "external50" in name:
        return "flash_api_e50"
    if "qwen3.6-35b" in text and "external50" in name:
        return "qwen35b_e50"
    if "qwen3.5-122b" in text and "external50" in name:
        return "qwen122b_e50"
    if "gpt-oss" in text and "external50" in name:
        return "oss120b_e50"
    if "qwen3.6-35b" in text and "v1" in name:
        return "qwen35b_v1_200"
    return name
