"""Process metrics from the filled obligation ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import AUDIT_FILE
from .common import LEDGER_FILE
from .common import VERIFICATION_CITED


def _load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def _row_repo_cited(row: dict[str, Any]) -> bool:
    evidence = row.get("repo_evidence")
    if not isinstance(evidence, dict):
        return False
    return _nonempty(evidence.get("path"))


def _row_impl_cited(row: dict[str, Any]) -> bool:
    evidence = row.get("implementation")
    if not isinstance(evidence, dict):
        return False
    return _nonempty(evidence.get("path"))


def _row_verification_cited(row: dict[str, Any]) -> bool:
    verification = row.get("verification")
    if not isinstance(verification, dict):
        return False
    status = str(verification.get("status") or "").strip().lower()
    return status == VERIFICATION_CITED or _nonempty(verification.get("citation"))


def collect_ledger_metrics(workspace_dir: str | Path) -> dict[str, Any]:
    """Summarize whether each frozen obligation has source and implementation evidence."""

    workspace = Path(workspace_dir).resolve()
    ledger_path = workspace / LEDGER_FILE
    ledger = _load_ledger(ledger_path)
    rows = [
        row
        for row in (ledger.get("obligations") or [])
        if isinstance(row, dict)
    ]
    frozen = [
        str(item)
        for item in (ledger.get("frozen_ids") or [])
        if str(item).strip()
    ]
    observed_ids = [str(row.get("id") or "").strip() for row in rows]
    observed_set = {item for item in observed_ids if item}
    frozen_set = set(frozen)
    missing_ids = sorted(frozen_set - observed_set) if frozen_set else []
    invented_ids = sorted(observed_set - frozen_set) if frozen_set else []

    repo_cited = sum(1 for row in rows if _row_repo_cited(row))
    impl_cited = sum(1 for row in rows if _row_impl_cited(row))
    both_cited = sum(
        1 for row in rows if _row_repo_cited(row) and _row_impl_cited(row)
    )
    verification_cited = sum(1 for row in rows if _row_verification_cited(row))
    total = len(rows)
    coverage_complete = (
        bool(total)
        and both_cited == total
        and not missing_ids
        and not invented_ids
    )
    return {
        "ledger_present": ledger_path.is_file(),
        "rows_total": total,
        "rows_repo_cited": repo_cited,
        "rows_implementation_cited": impl_cited,
        "rows_both_cited": both_cited,
        "rows_verification_cited": verification_cited,
        "coverage_complete": coverage_complete,
        "finished_with_gaps": ledger_path.is_file() and not coverage_complete,
        "missing_row_ids": missing_ids,
        "invented_row_ids": invented_ids,
        "checker_present": (workspace / "run_contract_check.py").is_file()
        or (workspace / "flb-contract-check").is_file()
        or (workspace / "run_cgvl_check.py").is_file(),
    }


def write_audit(
    workspace_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    payload = collect_ledger_metrics(workspace)
    target = Path(output_path) if output_path else workspace / AUDIT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
