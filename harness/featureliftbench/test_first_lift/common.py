"""Shared constants for Test-First Lift."""

from __future__ import annotations

CHARACTERIZATION_DIR = "characterization"
ORACLE_FILE = "oracle.json"
LOCK_FILE = "characterization.lock"
FREEZE_AUDIT_FILE = "test_first_lift_freeze.json"
PHASE_AUDIT_FILE = "test_first_lift_phase.json"
WRAPPER_NAME = "flb-test-first"
MAX_CASES = 15
MIN_CASES = 1
DEFAULT_CASE_TIMEOUT_SECONDS = 60
TEST_FIRST_LIFT_ENV = "FEATURELIFTBENCH_TEST_FIRST_LIFT"
