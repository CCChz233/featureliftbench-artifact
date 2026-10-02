"""Self-Authored Contract arm: model writes contracts, freeze, then implement.

Phase 0 — Optional upstream RUNTIME_FACTS (reuse exec_contract collect; no template pytest).
Phase A — Agent authors contracts/; author-gate (min tests + empty stub must fail).
Freeze  — Hash lock contracts/.
Phase B — Agent implements submission/; verify; optional repair (submission only).

See docs/archive/methods/METHOD_SELF_CONTRACT.md.
"""

from __future__ import annotations

from .audit import write_self_contract_audit
from .author_gate import evaluate_author_gate
from .common import SELF_CONTRACT_ENV
from .common import SELF_CONTRACT_PHASE_ENV
from .freeze import freeze_contracts
from .freeze import verify_contracts_frozen
from .workspace import author_task_appendix
from .workspace import implement_task_appendix
from .workspace import install_self_contract_workspace
from .workspace import openhands_author_appendix
from .workspace import openhands_implement_appendix
from .workspace import prepare_author_repair_workspace
from .workspace import prepare_impl_repair_workspace
from .workspace import reset_submission_dir

__all__ = [
    "SELF_CONTRACT_ENV",
    "SELF_CONTRACT_PHASE_ENV",
    "author_task_appendix",
    "evaluate_author_gate",
    "freeze_contracts",
    "implement_task_appendix",
    "install_self_contract_workspace",
    "openhands_author_appendix",
    "openhands_implement_appendix",
    "prepare_author_repair_workspace",
    "prepare_impl_repair_workspace",
    "reset_submission_dir",
    "verify_contracts_frozen",
    "write_self_contract_audit",
]
