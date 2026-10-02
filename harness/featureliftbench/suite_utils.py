"""Shared helpers for suite runs, re-evaluation, and analysis."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_FLAKE_PYTEST_MISSING = "No module named pytest"
EVAL_TOOLING_ERROR_PREFIX = "eval tooling failed"

ALL_RUN_STATUSES = frozenset(
    {"passed", "failed", "missing_submission", "not_evaluated", "invalid_task"}
)
DEFAULT_RETRY_ONLY_STATUSES = frozenset({"missing_submission", "failed", "not_evaluated"})
RATE_LIMIT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"rate limit",
        r"ratelimit",
        r"too many requests",
        r"\b429\b",
        r"quota exceeded",
        r"tpm limit",
    )
)

FAILURE_CLASSES = frozenset(
    {
        "passed",
        "agent_setup_failed",
        "rate_limited",
        "missing_submission",
        "eval_infra_failed",
        "model_failed",
        "invalid_task",
        "agent_step_limited",
    }
)


def resolve_suite_artifact_path(
    suite_dir: str | Path,
    task_id: str,
    relative_path: str | Path,
    recorded_path: object = None,
) -> Path:
    """Resolve a task artifact after a suite has moved between machines.

    Older suite files record absolute server paths.  The task-local path is the
    portable source of truth, so prefer it whenever it exists and only fall
    back to the recorded path for legacy layouts.
    """

    suite_path = Path(suite_dir)
    local_path = suite_path / task_id / Path(relative_path)
    if local_path.exists():
        return local_path

    if isinstance(recorded_path, (str, Path)) and str(recorded_path):
        candidate = Path(recorded_path)
        if candidate.exists():
            return candidate
        if not candidate.is_absolute():
            relative_candidate = suite_path / candidate
            if relative_candidate.exists():
                return relative_candidate

    return local_path


def parse_retry_only_statuses(value: str | None) -> frozenset[str]:
    """Parse a comma-separated list of run statuses eligible for agent retry."""

    if not value:
        return DEFAULT_RETRY_ONLY_STATUSES
    statuses = frozenset(part.strip() for part in value.split(",") if part.strip())
    if not statuses:
        return DEFAULT_RETRY_ONLY_STATUSES
    unknown = statuses - ALL_RUN_STATUSES
    if unknown:
        raise ValueError(
            f"unknown retry-only status values: {', '.join(sorted(unknown))}; "
            f"allowed: {', '.join(sorted(ALL_RUN_STATUSES))}"
        )
    return statuses


def load_retained_runs(
    suite_dir: str | Path | None,
    *,
    retain_statuses: frozenset[str] = frozenset({"passed"}),
) -> dict[str, dict[str, Any]]:
    """Load full task run.json payloads from a previous suite output directory."""

    if suite_dir is None:
        return {}
    base_dir = Path(suite_dir).resolve()
    suite_path = base_dir / "suite.json"
    if suite_path.is_file():
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        retained: dict[str, dict[str, Any]] = {}
        for entry in suite.get("runs", []):
            if not isinstance(entry, dict):
                continue
            status = entry.get("status")
            if not isinstance(status, str) or status not in retain_statuses:
                continue
            task_id = entry.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            run_json = base_dir / task_id / "run.json"
            if run_json.is_file():
                retained[task_id] = json.loads(run_json.read_text(encoding="utf-8"))
        return retained
    return _load_retained_runs_from_task_dirs(base_dir, retain_statuses=retain_statuses)


def _load_retained_runs_from_task_dirs(
    base_dir: Path,
    *,
    retain_statuses: frozenset[str],
) -> dict[str, dict[str, Any]]:
    """Fallback for mid-suite resume before suite.json is written."""

    retained: dict[str, dict[str, Any]] = {}
    if not base_dir.is_dir():
        return retained
    for task_dir in sorted(base_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        run_json = task_dir / "run.json"
        if not run_json.is_file():
            continue
        try:
            payload = json.loads(run_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        status = payload.get("status")
        if not isinstance(status, str) or status not in retain_statuses:
            continue
        retained[task_dir.name] = payload
    return retained


def evaluation_payload(eval_result: dict[str, Any] | None, eval_output_dir: Path) -> dict[str, Any]:
    if eval_result is None:
        return {
            "dir": str(eval_output_dir),
            "result_json": "",
            "status": "not-run",
            "scores": {},
            "resource_limited": False,
            "log_limit_exceeded": False,
            "docker_sandbox_error": False,
            "sandbox_backend": "",
        }
    sandbox = eval_result.get("sandbox") if isinstance(eval_result.get("sandbox"), dict) else {}
    return {
        "dir": str(eval_output_dir),
        "result_json": str(eval_output_dir / "result.json"),
        "status": eval_result.get("status", "failed"),
        "scores": eval_result.get("scores", {}),
        "build_pass": eval_result.get("build_pass"),
        "test_pass": eval_result.get("test_pass"),
        "resource_limited": _eval_result_has_flag(eval_result, "resource_limited"),
        "log_limit_exceeded": _eval_result_has_flag(eval_result, "log_limit_exceeded"),
        "docker_sandbox_error": bool(
            eval_result.get("docker_sandbox_error") or sandbox.get("docker_sandbox_error")
        ),
        "sandbox_backend": sandbox.get("backend", "") if isinstance(sandbox.get("backend"), str) else "",
    }


def run_status(
    *,
    validation_ok: bool,
    agent_passed: bool,
    submission_exists: bool,
    eval_result: dict[str, Any] | None,
) -> str:
    if not validation_ok:
        return "invalid_task"
    if not submission_exists:
        return "missing_submission"
    if eval_result is None:
        return "not_evaluated"
    if agent_passed and eval_result.get("status") == "passed":
        return "passed"
    return "failed"


def run_failure_class(run: dict[str, Any]) -> str:
    """Classify a run by root outcome for suite-level interpretation."""

    status = run.get("status")
    if status == "passed":
        return "passed"
    if status == "invalid_task":
        return "invalid_task"
    if _agent_result_has_step_limit(run):
        return "agent_step_limited"
    if is_rate_limit_failure(run):
        return "rate_limited"

    agent = run.get("agent") if isinstance(run.get("agent"), dict) else {}
    submission = run.get("submission") if isinstance(run.get("submission"), dict) else {}
    evaluation = run.get("evaluation") if isinstance(run.get("evaluation"), dict) else {}
    if _agent_had_zero_api_calls(run) and (
        not submission.get("exists", False) or not agent.get("passed", False)
    ):
        return "agent_setup_failed"
    if not submission.get("exists", False):
        return "missing_submission"
    if evaluation.get("docker_sandbox_error") is True:
        return "eval_infra_failed"
    if evaluation.get("status") in {"not-run", "not_evaluated"}:
        return "eval_infra_failed"
    return "model_failed"


def is_rate_limit_failure(result: dict[str, Any]) -> bool:
    chunks: list[str] = []
    agent = result.get("agent")
    if isinstance(agent, dict):
        usage = agent.get("usage")
        if isinstance(usage, dict):
            exit_status = usage.get("exit_status")
            if isinstance(exit_status, str) and exit_status:
                chunks.append(exit_status)
        for key in ("reason",):
            value = agent.get(key)
            if isinstance(value, str):
                chunks.append(value)
        for log_key in ("stderr_log", "stdout_log"):
            log_path = agent.get(log_key)
            if isinstance(log_path, str):
                path = Path(log_path)
                if path.is_file():
                    chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    errors = result.get("errors")
    if isinstance(errors, list):
        chunks.extend(str(item) for item in errors)
    text = "\n".join(chunks)
    return any(pattern.search(text) for pattern in RATE_LIMIT_PATTERNS)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_eval_flake(task_run_dir: Path) -> bool:
    """Return True when failure symptoms match known eval infrastructure flakes."""

    logs_dir = task_run_dir / "eval" / "logs"
    if logs_dir.is_dir():
        for name in ("public.stderr", "hidden.stderr", "eval_tooling.stderr", "eval_tooling_retry.stderr"):
            path = logs_dir / name
            if path.is_file() and EVAL_FLAKE_PYTEST_MISSING in path.read_text(encoding="utf-8", errors="ignore"):
                return True

    result_path = task_run_dir / "eval" / "result.json"
    if result_path.is_file():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        errors = result.get("errors")
        if isinstance(errors, list):
            for error in errors:
                if isinstance(error, str) and EVAL_TOOLING_ERROR_PREFIX in error:
                    return True
        eval_tooling = result.get("eval_tooling")
        if isinstance(eval_tooling, dict) and not eval_tooling.get("passed", True):
            return True

    return False


def functional_gate_value(run: dict[str, Any]) -> float | None:
    """Return the formal functional gate from full or compact suite records.

    Current compact suite entries retain ``final_score`` but omit the nested
    evaluator scores.  Since scoring v2 defines ``final_score`` as an exact
    compatibility alias for the binary functional gate, it is a safe fallback
    only when the value is exactly 0 or 1.
    """

    evaluation = run.get("evaluation")
    if isinstance(evaluation, dict):
        scores = evaluation.get("scores")
        if isinstance(scores, dict):
            value = scores.get("functional_gate")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    value = run.get("functional_gate")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    value = run.get("final_score")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and float(value) in {0.0, 1.0}
    ):
        return float(value)
    return None


def rebuild_suite_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    final_scores = [
        run.get("evaluation", {}).get("scores", {}).get("final_score")
        for run in runs
        if isinstance(run.get("evaluation"), dict)
    ]
    numeric_scores = [score for score in final_scores if isinstance(score, (int, float))]
    functional_values = [functional_gate_value(run) for run in runs]
    functional_evaluated = [value for value in functional_values if value is not None]
    functional_passed = sum(value == 1.0 for value in functional_evaluated)
    by_status: dict[str, int] = {}
    tasks_by_status: dict[str, list[str]] = {}
    for run in runs:
        status = run.get("status", "failed")
        if not isinstance(status, str):
            status = "failed"
        by_status[status] = by_status.get(status, 0) + 1
        task_id = run.get("task_id")
        if isinstance(task_id, str) and task_id:
            tasks_by_status.setdefault(status, []).append(task_id)
    for task_ids in tasks_by_status.values():
        task_ids.sort()
    failure_classes: dict[str, int] = {}
    tasks_by_failure_class: dict[str, list[str]] = {}
    for run in runs:
        failure_class = run_failure_class(run)
        failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1
        task_id = run.get("task_id")
        if isinstance(task_id, str) and task_id:
            tasks_by_failure_class.setdefault(failure_class, []).append(task_id)
    for task_ids in tasks_by_failure_class.values():
        task_ids.sort()
    summary: dict[str, Any] = {
        "total": len(runs),
        # ``passed`` is the historical end-to-end run status and is retained
        # for resume compatibility.  Papers and experiment reports must use
        # the explicit functional fields below.
        "passed": sum(1 for run in runs if run.get("status") == "passed"),
        "failed": sum(1 for run in runs if run.get("status") != "passed"),
        "run_status_passed": sum(1 for run in runs if run.get("status") == "passed"),
        "functional_passed": functional_passed,
        "functional_failed": len(runs) - functional_passed,
        "functional_evaluated": len(functional_evaluated),
        "functional_unknown": len(runs) - len(functional_evaluated),
        "functional_pass_rate": (
            round(functional_passed / len(runs), 6) if runs else 0.0
        ),
        "agent_failures": sum(1 for run in runs if not run.get("agent", {}).get("passed", False)),
        "missing_submissions": sum(
            1 for run in runs if not run.get("submission", {}).get("exists", False)
        ),
        "recovered_submissions": sum(
            1 for run in runs if run.get("submission", {}).get("recovered", False)
        ),
        "resource_limited_failures": sum(
            1 for run in runs if run.get("evaluation", {}).get("resource_limited") is True
        ),
        "log_limit_failures": sum(
            1
            for run in runs
            if run.get("evaluation", {}).get("log_limit_exceeded") is True
            or _agent_result_has_log_limit(run)
        ),
        "docker_sandbox_failures": sum(
            1 for run in runs if run.get("evaluation", {}).get("docker_sandbox_error") is True
        ),
        "average_final_score": (
            # The benchmark denominator is every assigned task. Missing
            # submissions and failed gates therefore contribute zero instead
            # of disappearing from the average.
            round(sum(numeric_scores) / len(runs), 6) if runs else 0.0
        ),
        "by_status": by_status,
        "tasks_by_status": tasks_by_status,
        "failure_classes": failure_classes,
        "tasks_by_failure_class": tasks_by_failure_class,
    }
    graph_runs = [
        run.get("repo_graph")
        for run in runs
        if isinstance(run.get("repo_graph"), dict)
    ]
    if graph_runs:
        summary["repo_graph"] = {
            "enabled_runs": len(graph_runs),
            "optional_tool_used_runs": sum(
                graph.get("optional_tool_used") is True for graph in graph_runs
            ),
            "support_queried_runs": sum(
                graph.get("support_queried") is True for graph in graph_runs
            ),
            "adoption_compliant_runs": sum(
                graph.get("adoption_compliant") is True for graph in graph_runs
            ),
            "task_closure_queried_runs": sum(
                graph.get("task_closure_queried") is True for graph in graph_runs
            ),
            "fresh_submission_check_runs": sum(
                graph.get("fresh_submission_check") is True for graph in graph_runs
            ),
            "query_count": sum(
                int(graph.get("query_count", 0))
                for graph in graph_runs
                if isinstance(graph.get("query_count", 0), int)
            ),
            "query_failure_count": sum(
                int(graph.get("query_failure_count", 0))
                for graph in graph_runs
                if isinstance(graph.get("query_failure_count", 0), int)
            ),
            "protocol_violation_runs": sum(
                graph.get("protocol_violation") is True for graph in graph_runs
            ),
        }
    return summary


def compact_agent_usage(usage: dict[str, Any]) -> dict[str, Any]:
    if usage.get("available") is not True:
        compact: dict[str, Any] = {
            "available": False,
            "reason": usage.get("reason", "usage unavailable"),
        }
        if isinstance(usage.get("source"), str):
            compact["source"] = usage["source"]
        return compact

    compact = {"available": True}
    for key in (
        "assistant_steps",
        "api_calls",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "effective_uncached_prompt_tokens",
        "tool_alias_normalizations",
        "trace_tokens",
        "billed_tokens",
    ):
        value = usage.get(key)
        if isinstance(value, int):
            compact[key] = value
    context_audit = usage.get("context_audit")
    if isinstance(context_audit, dict):
        compact_audit: dict[str, Any] = {}
        for key in (
            "context_window_tokens",
            "reserved_output_tokens",
            "max_allowed_prompt_tokens",
            "max_prompt_tokens_per_call",
            "max_total_tokens_per_call",
            "condenser_trigger_tokens",
            "condenser_target_tokens",
            "condenser_keep_first",
            "condenser_max_events",
            "condenser_attention_window",
            "condensation_events",
            "forgotten_event_count",
            "condensation_summaries_nonempty",
        ):
            value = context_audit.get(key)
            if isinstance(value, int):
                compact_audit[key] = value
        for key in ("context_violation", "usage_unverified"):
            value = context_audit.get(key)
            if isinstance(value, bool):
                compact_audit[key] = value
        compression_mode = context_audit.get("compression_mode")
        if isinstance(compression_mode, str) and compression_mode:
            compact_audit["compression_mode"] = compression_mode
        condenser_kind = context_audit.get("condenser_kind")
        if isinstance(condenser_kind, str) and condenser_kind:
            compact_audit["condenser_kind"] = condenser_kind
        attention_window = context_audit.get("attention_window")
        if isinstance(attention_window, int):
            compact_audit["attention_window"] = attention_window
        if compact_audit:
            compact["context_audit"] = compact_audit
    tool_summary = usage.get("tool_summary")
    if isinstance(tool_summary, dict):
        compact_tool: dict[str, Any] = {}
        for key in (
            "total_actions",
            "success_actions",
            "failed_actions",
            "blocked_actions",
            "timeout_actions",
            "error_actions",
        ):
            value = tool_summary.get(key)
            if isinstance(value, int):
                compact_tool[key] = value
        for key in (
            "actions_enabled",
        ):
            value = tool_summary.get(key)
            if isinstance(value, bool):
                compact_tool[key] = value
        for key in (
            "final_check_status",
            "public_tests_status",
        ):
            value = tool_summary.get(key)
            if isinstance(value, str):
                compact_tool[key] = value
        if compact_tool:
            compact["tool_summary"] = compact_tool
    return compact


def effective_agent_usage_for_run(run: dict[str, Any]) -> dict[str, Any]:
    """Use all closure/V2 phases when present; otherwise use the primary agent usage."""

    closure = run.get("contract_closure")
    if isinstance(closure, dict):
        totals = closure.get("usage_totals")
        if isinstance(totals, dict) and totals.get("available") is True:
            return totals
    v2 = run.get("adaptive_budget_v2")
    if isinstance(v2, dict):
        totals = v2.get("usage_totals")
        if isinstance(totals, dict) and totals.get("available") is True:
            return totals
    agent = run.get("agent") if isinstance(run.get("agent"), dict) else {}
    usage = agent.get("usage") if isinstance(agent.get("usage"), dict) else {}
    return usage


def compact_suite_run_entry(run: dict[str, Any]) -> dict[str, Any]:
    usage = effective_agent_usage_for_run(run)
    evaluation = run.get("evaluation") if isinstance(run.get("evaluation"), dict) else {}
    scores = evaluation.get("scores") if isinstance(evaluation.get("scores"), dict) else {}
    submission = run.get("submission") if isinstance(run.get("submission"), dict) else {}
    entry: dict[str, Any] = {
        "task_id": run.get("task_id", ""),
        "status": run.get("status", "failed"),
        "failure_class": run_failure_class(run),
        "run_json": run.get("run_json", ""),
        "result_json": evaluation.get("result_json", ""),
        "final_score": scores.get("final_score", 0.0),
        "agent_usage": compact_agent_usage(usage),
    }
    benchmark_freeze = run.get("benchmark_freeze")
    if isinstance(benchmark_freeze, dict) and benchmark_freeze:
        entry["benchmark_freeze"] = {
            key: benchmark_freeze.get(key)
            for key in (
                "policy_id",
                "freeze_id",
                "task_revision",
                "source_snapshot_id",
                "source_tree_sha256",
            )
        }
    source = run.get("source")
    if isinstance(source, dict) and source:
        entry["source"] = {
            key: source.get(key)
            for key in (
                "policy_id",
                "source_repo_id",
                "source_snapshot_id",
                "source_digest",
                "archive_sha256",
                "snapshot_scope",
                "status",
            )
        }
    conditions = run.get("experiment_conditions")
    if isinstance(conditions, dict) and conditions:
        entry["experiment_conditions"] = conditions
    if submission.get("recovered") is True:
        entry["submission_recovered"] = True
    for key in ("resource_limited", "log_limit_exceeded", "docker_sandbox_error", "sandbox_backend"):
        value = evaluation.get(key)
        if value:
            entry[key] = value
    if _agent_result_has_log_limit(run):
        entry["log_limit_exceeded"] = True
    repo_graph = run.get("repo_graph")
    if isinstance(repo_graph, dict):
        entry["repo_graph"] = compact_repo_graph_usage(repo_graph)
    return entry


def compact_repo_graph_usage(usage: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "query_count",
        "successful_query_count",
        "query_failure_count",
        "query_chars",
        "bootstrap_chars",
        "submission_revision",
    ):
        value = usage.get(key)
        if isinstance(value, int):
            compact[key] = value
    for key in (
        "task_closure_queried",
        "fresh_submission_check",
        "adoption_compliant",
        "optional_tool_used",
        "support_queried",
        "search_queried",
        "inspect_queried",
        "protocol_violation",
    ):
        value = usage.get(key)
        if isinstance(value, bool):
            compact[key] = value
    for key in ("status", "mechanism_status", "snapshot_id", "rsg_bootstrap"):
        value = usage.get(key)
        if isinstance(value, str) and value:
            compact[key] = value
    budget = usage.get("rsg_budget_tokens")
    if isinstance(budget, int):
        compact["rsg_budget_tokens"] = budget
    return compact


def _eval_result_has_flag(eval_result: dict[str, Any], flag: str) -> bool:
    if eval_result.get(flag) is True:
        return True
    for key in (
        "dependency_install",
        "eval_tooling",
        "submission_install",
        "build",
        "public_tests",
        "hidden_tests",
    ):
        payload = eval_result.get(key)
        if isinstance(payload, dict) and payload.get(flag) is True:
            return True
    return False


def _agent_result_has_log_limit(run: dict[str, Any]) -> bool:
    agent = run.get("agent")
    if not isinstance(agent, dict):
        return False
    if agent.get("log_limit_exceeded") is True:
        return True
    usage = agent.get("usage")
    if not isinstance(usage, dict):
        return False
    return usage.get("exit_status") == "log_limit_exceeded"


def _agent_result_has_step_limit(run: dict[str, Any]) -> bool:
    agent = run.get("agent")
    if not isinstance(agent, dict):
        return False
    usage = agent.get("usage")
    if not isinstance(usage, dict):
        return False
    return usage.get("exit_status") == "step_limit_exceeded"


def _agent_had_zero_api_calls(run: dict[str, Any]) -> bool:
    agent = run.get("agent")
    if not isinstance(agent, dict):
        return False
    usage = agent.get("usage")
    if not isinstance(usage, dict) or usage.get("available") is not True:
        return False
    api_calls = usage.get("api_calls")
    return isinstance(api_calls, int) and api_calls <= 0
