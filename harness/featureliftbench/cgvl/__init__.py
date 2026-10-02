"""Contract-Guided Verification Loop (CGVL).

Harness-expanded public-contract matrix, discriminating cells, and an evidence
gate. Screening only. See docs/archive/methods/METHOD_CGVL.md.
"""

from __future__ import annotations

from .audit import collect_workspace_metrics
from .audit import write_audit
from .common import AUDIT_FILE
from .common import CASES_DIR
from .common import CHECK_LEDGER
from .common import CHECKER_NAME
from .common import EVIDENCE_FILE
from .common import FINISH_GATE_FILE
from .common import MATRIX_FILE
from .expand import build_cgvl_matrix
from .expand import flatten_required_api
from .expand import required_cells
from .workspace import install_cgvl_workspace
from .workspace import openhands_appendix
from .workspace import task_appendix

__all__ = [
    "AUDIT_FILE",
    "CASES_DIR",
    "CHECK_LEDGER",
    "CHECKER_NAME",
    "EVIDENCE_FILE",
    "FINISH_GATE_FILE",
    "MATRIX_FILE",
    "build_cgvl_matrix",
    "collect_workspace_metrics",
    "flatten_required_api",
    "install_cgvl_workspace",
    "openhands_appendix",
    "required_cells",
    "task_appendix",
    "write_audit",
]
