"""Test-First Lift: agent-authored paired characterization + harness oracle freeze.

See docs/archive/methods/METHOD_TEST_FIRST_LIFT.md.
"""

from __future__ import annotations

from .audit import collect_workspace_metrics
from .audit import compute_method_freeze
from .audit import write_phase_audit
from .common import CHARACTERIZATION_DIR
from .common import LOCK_FILE
from .common import ORACLE_FILE
from .common import PHASE_AUDIT_FILE
from .common import TEST_FIRST_LIFT_ENV
from .common import WRAPPER_NAME
from .freeze import freeze_characterization
from .freeze import verify_characterization
from .freeze import verify_characterization_frozen
from .workspace import install_test_first_lift_workspace
from .workspace import openhands_appendix
from .workspace import task_appendix

__all__ = [
    "CHARACTERIZATION_DIR",
    "LOCK_FILE",
    "ORACLE_FILE",
    "PHASE_AUDIT_FILE",
    "TEST_FIRST_LIFT_ENV",
    "WRAPPER_NAME",
    "collect_workspace_metrics",
    "compute_method_freeze",
    "freeze_characterization",
    "install_test_first_lift_workspace",
    "openhands_appendix",
    "task_appendix",
    "verify_characterization",
    "verify_characterization_frozen",
    "write_phase_audit",
]
