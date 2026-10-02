"""Frozen constants for the current paper token-efficiency analysis."""

from __future__ import annotations

METHOD_VERSION = "token_efficiency_current.v2"
ANALYSIS_SEED = 20260916
BOOTSTRAP_REPLICATES = 10_000
DEFAULT_WORKERS = 2

PINNED_EVAL_IMAGE = "featureliftbench-eval:python200-prime-212930ea"
PINNED_REPLAY_IMAGE = "featureliftbench-agent:python200-prime-212930ea"
FORBIDDEN_EVAL_IMAGE = "featureliftbench-eval:latest"

ACCOUNTING_TOTAL = "input_output_total"
ACCOUNTING_MAIN_TABLE = "main_table"

CONFIG_ORDER = (
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    "gpt-5.6-luna",
    "glm-5.3-flash",
    "qwen3.6-35b-a3b-fp8",
    "gpt-oss-120b",
)

PILOT_CONFIGS = ("deepseek-v4-pro", "deepseek-v4-flash")
LIFT_TYPES = ("Direct", "Adapted", "Composite")
PILOT_PASS_QUOTA = {"Direct": 2, "Adapted": 2, "Composite": 1}
PILOT_FAIL_QUOTA = {"Direct": 2, "Adapted": 2, "Composite": 1}

EDITOR_WRITE_COMMANDS = frozenset(
    {"create", "str_replace", "insert", "write", "edit", "undo_edit"}
)
MUTATING_TOOLS = frozenset({"file_editor", "terminal", "bash", "execute_bash"})
NON_MUTATING_TOOLS = frozenset(
    {"view", "think", "task_tracker", "finish", "task", "browser"}
)

EVAL_CODE_RELATIVE = (
    "harness/featureliftbench/evaluator.py",
    "harness/featureliftbench/docker_eval.py",
    "harness/featureliftbench/evaluation_capsule.py",
    "harness/featureliftbench/scoring.py",
    "harness/featureliftbench/compactness.py",
    "harness/featureliftbench/checks.py",
    "harness/featureliftbench/metrics.py",
    "harness/featureliftbench/dependency_install.py",
)

IGNORE_NAME_PARTS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store"}
)
IGNORE_SUFFIXES = (".pyc", ".pyo")

RUN_MANIFEST_FIELDS = (
    "run_id",
    "configuration",
    "task_id",
    "suite_id",
    "source_run_dir",
    "mapped_run_dir",
    "final_pass",
    "lift_type",
    "identity_status",
    "events_available",
    "call_usage_available",
    "final_eval_available",
    "initial_state_available",
    "final_artifact_available",
    "path_identity_ok",
)

RUN_METRICS_FIELDS = (
    "method_version",
    "run_id",
    "configuration",
    "task_id",
    "lift_type",
    "final_pass",
    "identity_status",
    "replay_status",
    "final_tree_matches",
    "final_eval_matches",
    "full_timeline_covered",
    "unique_states",
    "evaluated_states",
    "unresolved_states",
    "accounting_basis",
    "token_usage_status",
    "token_alignment_status",
    "total_tokens",
    "original_steps",
    "sufficiency_status",
    "first_pass_state_index",
    "first_pass_hash",
    "first_pass_tokens",
    "first_pass_tokens_lower",
    "first_pass_tokens_upper",
    "first_pass_fraction",
    "post_sufficiency_tokens",
    "post_sufficiency_fraction",
    "post_sufficiency_fraction_lower",
    "post_sufficiency_fraction_upper",
    "post_sufficiency_mutations",
    "post_sufficiency_failure_seen",
    "ever_pass_final_fail",
    "stable_first_pass_state_index",
    "stable_first_pass_tokens",
    "stable_post_fraction",
    "stable_status",
    "include_psf_primary",
    "include_effort",
    "include_failure_history",
    "exclusion_reason_psf_primary",
    "exclusion_reason_effort",
    "exclusion_reason_failure_history",
    "missing_reason",
    "notes",
)
