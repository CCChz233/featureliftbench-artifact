"""Spec-grounded adversarial self-test: executable public-spec checklist.

Not self-reflection, not Public-feedback, not TFL freeze-before-implement.
See docs/archive/methods/METHOD_SPEC_ADVERSARIAL.md.
"""

from __future__ import annotations

from .audit import collect_workspace_metrics
from .audit import write_audit
from .common import AUDIT_FILE
from .common import CASES_DIR
from .common import CHECK_LEDGER
from .common import CHECKER_NAME
from .common import MATRIX_FILE
from .common import SPEC_ADVERSARIAL_ENV
from .matrix import build_contract_matrix
from .matrix import flatten_required_api_paths
from .matrix import scenario_behavior_ids
from .workspace import install_spec_adversarial_workspace
from .workspace import openhands_appendix
from .workspace import task_appendix

__all__ = [
    "AUDIT_FILE",
    "CASES_DIR",
    "CHECK_LEDGER",
    "CHECKER_NAME",
    "MATRIX_FILE",
    "SPEC_ADVERSARIAL_ENV",
    "build_contract_matrix",
    "collect_workspace_metrics",
    "flatten_required_api_paths",
    "install_spec_adversarial_workspace",
    "openhands_appendix",
    "scenario_behavior_ids",
    "task_appendix",
    "write_audit",
]
