"""Audit helpers for Test-First Lift."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .common import FREEZE_AUDIT_FILE
from .common import LOCK_FILE
from .common import ORACLE_FILE
from .common import PHASE_AUDIT_FILE
from .freeze import verify_characterization
from .freeze import verify_characterization_frozen


def compute_method_freeze() -> dict[str, Any]:
    """Record TFL package + prompt appendix digests for formal audit."""

    package_root = Path(__file__).resolve().parent
    files: dict[str, str] = {}
    tree = hashlib.sha256()
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(package_root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[rel] = digest
        tree.update(rel.encode("utf-8"))
        tree.update(b"\0")
        tree.update(bytes.fromhex(digest))
    from .workspace import openhands_appendix
    from .workspace import task_appendix

    task_text = task_appendix()
    oh_text = openhands_appendix()
    return {
        "schema_version": "featureliftbench.test_first_lift_method_freeze.v1",
        "tfl_package_tree_sha256": tree.hexdigest(),
        "tfl_package_files": files,
        "tfl_task_appendix_sha256": hashlib.sha256(task_text.encode("utf-8")).hexdigest(),
        "tfl_openhands_appendix_sha256": hashlib.sha256(oh_text.encode("utf-8")).hexdigest(),
    }


def collect_workspace_metrics(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    freeze_path = workspace / FREEZE_AUDIT_FILE
    freeze_audit: dict[str, Any] = {}
    if freeze_path.is_file():
        try:
            payload = json.loads(freeze_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                freeze_audit = payload
        except json.JSONDecodeError:
            freeze_audit = {"ok": False, "error": "invalid freeze audit json"}

    frozen = verify_characterization_frozen(workspace)
    verify: dict[str, Any] | None = None
    if frozen.get("ok"):
        verify = verify_characterization(workspace)

    freeze_success = bool(freeze_audit.get("freeze_success") or freeze_audit.get("ok"))
    characterization_pass = bool((verify or {}).get("characterization_pass"))
    return {
        # Phase A / Phase B intermediate metrics — never substitute for formal Functional.
        "freeze_success": freeze_success,
        "characterization_pass": characterization_pass,
        "valid_case_count": int(freeze_audit.get("valid_case_count") or 0),
        "required_api_coverage": freeze_audit.get("required_api_coverage"),
        "lock_schema": frozen.get("lock_schema"),
        "freeze_audit": freeze_audit,
        "frozen": frozen,
        "verify": verify,
        "has_oracle": (workspace / ORACLE_FILE).is_file(),
        "has_lock": (workspace / LOCK_FILE).is_file(),
    }


def _formal_metrics(evaluation: dict[str, Any] | None) -> dict[str, Any]:
    """Extract formal evaluator metrics (test-blind Functional).

    Missing evaluation is still recorded so freeze-fail / no-submission runs
    remain in the suite denominator with formal_functional=null/false.
    """

    if not isinstance(evaluation, dict) or not evaluation:
        return {
            "formal_evaluated": False,
            "formal_functional": None,
            "formal_functional_gate": None,
            "formal_status": "not_evaluated",
            "formal_reason": "no_submission_or_eval_skipped",
        }
    scores = evaluation.get("scores") if isinstance(evaluation.get("scores"), dict) else {}
    gate = scores.get("functional_gate")
    if gate is None:
        gate = evaluation.get("functional_gate")
    functional = evaluation.get("functional_pass")
    if functional is None and gate is not None:
        try:
            functional = float(gate) >= 1.0
        except (TypeError, ValueError):
            functional = None
    status = evaluation.get("status")
    return {
        "formal_evaluated": True,
        "formal_functional": functional,
        "formal_functional_gate": gate,
        "formal_status": status,
        "formal_reason": evaluation.get("reason") or evaluation.get("error"),
    }


def write_phase_audit(
    output_dir: str | Path,
    *,
    workspace_dir: str | Path,
    agent_result: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
    submission_exists: bool | None = None,
) -> dict[str, Any]:
    metrics = collect_workspace_metrics(workspace_dir)
    formal = _formal_metrics(evaluation)
    payload = {
        "schema_version": "featureliftbench.test_first_lift_phase.v2",
        "arm": "test_first_lift",
        "metrics_separated": {
            "freeze_success": metrics["freeze_success"],
            "characterization_pass": metrics["characterization_pass"],
            "formal_functional": formal["formal_functional"],
        },
        "method_freeze": compute_method_freeze(),
        **metrics,
        **formal,
        "submission_exists": submission_exists,
        "included_in_suite_denominator": True,
        "agent": agent_result or {},
    }
    path = Path(output_dir).resolve() / PHASE_AUDIT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
