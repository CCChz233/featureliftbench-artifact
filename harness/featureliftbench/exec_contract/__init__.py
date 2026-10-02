"""Execution-Guided Contract arm: record upstream runtime facts as executable contracts.

Phase 0 — Run targeted upstream tests under instrumentation; synthesize contracts/.
Phase 1 — Agent implements featurelifted with RUNTIME_FACTS + contracts available.
Phase 2 — Verify contracts against submission (optional one repair round), then formal eval.

See docs/archive/methods/METHOD_EXEC_CONTRACT.md.
"""

from __future__ import annotations

from .audit import compute_contract_gate_ok
from .audit import compute_evidence_gate_ok
from .audit import evidence_gate_failures
from .audit import write_exec_contract_audit
from .collect import collect_upstream_runtime
from .synthesize import synthesize_contracts
from .verify import verify_submission_contracts
from .workspace import (
    EXEC_CONTRACT_ENV,
    deactivate_exec_contract_workspace,
    install_exec_contract_workspace,
    phase1_task_appendix,
    prepare_repair_workspace,
)

__all__ = [
    "EXEC_CONTRACT_ENV",
    "collect_upstream_runtime",
    "compute_contract_gate_ok",
    "compute_evidence_gate_ok",
    "deactivate_exec_contract_workspace",
    "evidence_gate_failures",
    "install_exec_contract_workspace",
    "phase1_task_appendix",
    "prepare_repair_workspace",
    "synthesize_contracts",
    "verify_submission_contracts",
    "write_exec_contract_audit",
]
