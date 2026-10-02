"""Process metrics for CGVL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import AUDIT_FILE
from .common import CASES_DIR
from .common import CHECK_LEDGER
from .common import FINISH_GATE_FILE
from .common import MATRIX_FILE
from .expand import required_cells


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def collect_workspace_metrics(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    ledger_path = workspace / CHECK_LEDGER
    if not ledger_path.is_file():
        alt = workspace.parent / "agent" / "cgvl_check.jsonl"
        if alt.is_file():
            ledger_path = alt
    records = _load_jsonl(ledger_path)
    matrix_path = workspace / MATRIX_FILE
    matrix = (
        json.loads(matrix_path.read_text(encoding="utf-8"))
        if matrix_path.is_file()
        else {}
    )
    expected = [
        str(cell.get("id") or "")
        for cell in required_cells(matrix)
        if cell.get("id")
    ]
    filled = 0
    undetermined = 0
    for cell_id in expected:
        case_path = workspace / CASES_DIR / f"{cell_id}.py"
        if not case_path.is_file():
            continue
        text = case_path.read_text(encoding="utf-8", errors="replace")
        if "FILLED = True" in text or "FILLED=True" in text:
            filled += 1
        if "UNDETERMINED = True" in text or "UNDETERMINED=True" in text:
            undetermined += 1
    last = records[-1] if records else {}
    checker_ok = bool(last.get("ok")) if records else False
    last_cells = [
        row
        for row in (last.get("cell_rows") or [])
        if isinstance(row, dict)
    ]
    public_entry_ok = sum(1 for row in last_cells if row.get("public_entry_called"))
    assertion_count = sum(
        len(row.get("assertions") or []) for row in last_cells if isinstance(row, dict)
    )
    counterexample_count = sum(
        len(row.get("mutants_killed") or []) for row in last_cells if isinstance(row, dict)
    )
    isolation_rows = [
        row for row in (last.get("isolation_rows") or []) if isinstance(row, dict)
    ]
    finish_gate_path = workspace / FINISH_GATE_FILE
    if not finish_gate_path.is_file():
        alt_gate = workspace.parent / "agent" / "cgvl_finish_gate.json"
        if alt_gate.is_file():
            finish_gate_path = alt_gate
    finish_gate: dict[str, Any] = {}
    if finish_gate_path.is_file():
        try:
            loaded_gate = json.loads(finish_gate_path.read_text(encoding="utf-8"))
            if isinstance(loaded_gate, dict):
                finish_gate = loaded_gate
        except json.JSONDecodeError:
            finish_gate = {}
    return {
        "checker_ran": bool(records),
        "checker_runs": len(records),
        "checker_ok": checker_ok if records else False,
        "last_red_count": int(last.get("red_count") or 0) if records else None,
        "last_green_count": int(last.get("green_count") or 0) if records else None,
        "cells_expected": len(expected),
        "cells_filled": filled,
        "cells_undetermined": undetermined,
        "all_required_filled": bool(expected) and filled >= len(expected),
        "public_entry_cells": public_entry_ok,
        "assertion_records": assertion_count,
        "counterexamples_killed": counterexample_count,
        "isolation_ok": bool(isolation_rows) and all(
            bool(row.get("ok")) for row in isolation_rows
        ),
        "finished_while_red": bool(records) and not checker_ok,
        "matrix_present": matrix_path.is_file(),
        "finish_allowed": bool(last.get("finish_allowed")) if records else False,
        "runtime_finish_gate_ran": bool(finish_gate),
        "runtime_finish_gate_ok": bool(finish_gate.get("ok")) if finish_gate else False,
    }


def write_audit(
    workspace_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    payload = collect_workspace_metrics(workspace)
    target = Path(output_path) if output_path else workspace / AUDIT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
