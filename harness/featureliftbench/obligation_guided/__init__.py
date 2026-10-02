"""Obligation-Guided Feature Lifting: public-contract ledger, not self-tests.

See docs/METHOD_OBLIGATION_GUIDED.md.
"""

from __future__ import annotations

from .audit import collect_ledger_metrics
from .audit import write_audit
from .common import AUDIT_FILE
from .common import LEDGER_FILE
from .common import OBLIGATION_GUIDED_ENV
from .ledger import build_obligation_ledger
from .ledger import flatten_required_api_paths
from .workspace import install_obligation_guided_workspace
from .workspace import openhands_appendix
from .workspace import task_appendix

__all__ = [
    "AUDIT_FILE",
    "LEDGER_FILE",
    "OBLIGATION_GUIDED_ENV",
    "build_obligation_ledger",
    "collect_ledger_metrics",
    "flatten_required_api_paths",
    "install_obligation_guided_workspace",
    "openhands_appendix",
    "task_appendix",
    "write_audit",
]
