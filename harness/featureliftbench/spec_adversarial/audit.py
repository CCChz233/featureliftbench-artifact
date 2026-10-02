"""Process metrics for Spec-grounded adversarial self-test."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import AUDIT_FILE
from .common import CASES_DIR
from .common import CHECK_LEDGER
from .common import MATRIX_FILE


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
    """Summarize checker runs and stub fill state from the agent workspace."""

    workspace = Path(workspace_dir).resolve()
    ledger_path = workspace / CHECK_LEDGER
    if not ledger_path.is_file():
        # Checker writes under workspace/agent/; suite may also copy to task/agent/.
        alt = workspace.parent / "agent" / "contract_check.jsonl"
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
        str(row.get("id") or "")
        for row in matrix.get("behaviors") or []
        if isinstance(row, dict) and row.get("needs_scenario") and row.get("id")
    ]
    filled = 0
    for behavior_id in expected:
        case_path = workspace / CASES_DIR / f"{behavior_id}.py"
        if not case_path.is_file():
            continue
        text = case_path.read_text(encoding="utf-8", errors="replace")
        if "FILLED = True" in text or "FILLED=True" in text:
            filled += 1

    last = records[-1] if records else {}
    checker_ok = bool(last.get("ok")) if records else False
    oracle_used = any(
        bool(row.get("oracle_import"))
        or any(
            scenario.get("oracle_compared")
            for scenario in (row.get("scenario_rows") or [])
            if isinstance(scenario, dict)
        )
        for row in records
    )
    return {
        "checker_ran": bool(records),
        "checker_runs": len(records),
        "checker_ok": checker_ok if records else False,
        "last_red_count": int(last.get("red_count") or 0) if records else None,
        "last_green_count": int(last.get("green_count") or 0) if records else None,
        "oracle_used": oracle_used,
        "stubs_expected": len(expected),
        "stubs_filled": filled,
        "all_stubs_filled": bool(expected) and filled >= len(expected),
        "finished_while_red": bool(records) and not checker_ok,
        "matrix_present": matrix_path.is_file(),
    }


def write_audit(
    workspace_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    payload = collect_workspace_metrics(workspace)
    target = Path(output_path) if output_path else workspace / AUDIT_FILE
    # Prefer writing next to agent artifacts when called from the runner.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
