"""Identity checks against the selected official (configuration, task) pair."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .scope import OfficialRun
from .util import read_json


@dataclass
class IdentityResult:
    status: str
    path_identity_ok: bool
    run_task_id: str
    dirname_task_id: str
    eval_task_id: str
    workspace_task_id: str
    notes: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_identity(run: OfficialRun) -> IdentityResult:
    mapped = Path(run.mapped_run_dir)
    dirname = mapped.name if mapped.exists() else ""
    run_task_id = ""
    eval_task_id = ""
    workspace_task_id = ""
    notes: list[str] = []
    run_json = mapped / "run.json"
    if run_json.is_file():
        try:
            payload = read_json(run_json)
            run_task_id = str(payload.get("task_id") or "")
        except (OSError, ValueError, json.JSONDecodeError):
            notes.append("run_json_unreadable")
    else:
        notes.append("run_json_missing")
    result_json = mapped / "eval" / "result.json"
    if result_json.is_file():
        try:
            payload = read_json(result_json)
            eval_task_id = str(payload.get("task_id") or "")
        except (OSError, ValueError, json.JSONDecodeError):
            notes.append("eval_json_unreadable")
    metadata_path = mapped / "workspace" / "metadata.json"
    if metadata_path.is_file():
        try:
            payload = read_json(metadata_path)
            workspace_task_id = str(payload.get("task_id") or "")
        except (OSError, ValueError, json.JSONDecodeError):
            notes.append("workspace_metadata_unreadable")

    ids = {
        "expected": run.task_id,
        "dirname": dirname or None,
        "run_json": run_task_id or None,
        "eval": eval_task_id or None,
        "workspace": workspace_task_id or None,
    }
    present = {key: value for key, value in ids.items() if value}
    conflict = len(set(present.values())) > 1
    path_ok = dirname == run.task_id and mapped.is_dir()
    if conflict:
        status = "identity_conflict"
        notes.append("task_id_mismatch:" + ",".join(f"{k}={v}" for k, v in present.items()))
    elif not path_ok:
        status = "identity_unresolved"
        notes.append("mapped_directory_missing_or_renamed")
    elif run_task_id != run.task_id:
        status = "identity_unresolved"
    else:
        status = "ok"
    return IdentityResult(
        status=status,
        path_identity_ok=path_ok,
        run_task_id=run_task_id,
        dirname_task_id=dirname,
        eval_task_id=eval_task_id,
        workspace_task_id=workspace_task_id,
        notes="; ".join(notes),
    )
