"""Tests for audit_output_imports.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "harness" / "scripts" / "audit_output_imports.py"


def _run_audit(task_dir: Path) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), str(task_dir), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    reports = json.loads(result.stdout)
    assert len(reports) == 1
    return reports[0]


def test_iniconfig_output_import_covers_public_tests() -> None:
    task_dir = _REPO_ROOT / "benchmark" / "sanity" / "iniconfig__parse_config__001"
    report = _run_audit(task_dir)
    assert report["ok"] is True
    assert "IniConfig" in report["test_imports"]


def test_pytest_mark_expression_no_l1_gap_after_metadata_fix() -> None:
    task_dir = _REPO_ROOT / "benchmark" / "tasks" / "pytest__mark_expression_core__001"
    report = _run_audit(task_dir)
    assert report["ok"] is True
    assert "Scanner" in report["output_imports"] or any(
        "Scanner" in item for item in report["output_imports"]
    )
