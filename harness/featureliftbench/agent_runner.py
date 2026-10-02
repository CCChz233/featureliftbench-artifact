"""Agent workspace preparation and end-to-end run orchestration."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .task_render import render_agent_workspace_task
from .task_spec import SPEC_STATUS_COMPLIANT, get_spec_status
from .ablation import AblationOptions, ablation_options_from_env
from .active_agent_processes import terminate_active_agent_processes
from .agent_adapters import AgentRunConfig
from .agent_adapters import AgentRunContext
from .agent_adapters import get_agent_adapter
from .agent_docker import DEFAULT_AGENT_IMAGE
from .agent_docker import run_agent_in_docker
from .benchmark_freeze import benchmark_freeze_provenance
from .contract_closure_gate.common import LITE_V1_SILENT_FINISH_ENV
from .docker_eval import DEFAULT_EVAL_IMAGE
from .docker_eval import evaluate_submission_docker
from .evaluator import evaluate_submission
from .metadata import load_metadata
from .paths import resolve_task_input
from .pruned_source import materialize_pruned_task_source
from .pruned_source import pruned_source_provenance
from .repo_graph.policy import RepoGraphPolicy
from .repo_graph.runtime import RepoGraphRunState
from .repo_graph.runtime import append_repo_graph_prompt
from .repo_graph.runtime import finalize_repo_graph
from .repo_graph.runtime import initialize_repo_graph
from .suite_utils import ALL_RUN_STATUSES
from .suite_utils import DEFAULT_RETRY_ONLY_STATUSES
from .suite_utils import compact_suite_run_entry
from .suite_utils import effective_agent_usage_for_run
from .suite_utils import evaluation_payload as _evaluation_payload
from .suite_utils import load_retained_runs
from .suite_utils import rebuild_suite_summary
from .suite_utils import run_status as _run_status
from .source_ablation import VISIBLE_INVENTORY_NAME
from .source_ablation import assert_contract_only_workspace
from .source_ablation import contract_only_implementation_scope
from .source_ablation import experiment_condition_fields as source_ablation_condition_fields
from .source_ablation import is_contract_only
from .source_ablation import records_source_ablation
from .source_ablation import render_contract_only_agent_workspace_task
from .source_ablation import write_visible_workspace_inventory
from .source_archive import (
    materialize_task_source,
    source_provenance_for_task,
)
from .task_discovery import discover_main_task_dirs
from .suite_progress import SuiteBatchProgressManager
from .suite_progress import live_suite_progress
from .validate import validate_runnable_task

USAGE_SUM_FIELDS = (
    "assistant_steps",
    "total_messages",
    "api_calls",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "trace_tokens",
    "billed_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "effective_uncached_prompt_tokens",
    "tool_alias_normalizations",
)

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

# SiliconFlow TPM limits use a rolling 60s window; wait long enough to clear it.
RATE_LIMIT_RETRY_WAIT_SECONDS = 65.0
TRANSIENT_API_RETRY_WAIT_SECONDS = {
    "rate_limit": RATE_LIMIT_RETRY_WAIT_SECONDS,
    "rate_limited": RATE_LIMIT_RETRY_WAIT_SECONDS,
    "invalid_encrypted_content": 8.0,
    "tool_validation_error": 2.0,
}
ENCRYPTED_CONTENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"invalid_encrypted",
        r"encrypted content could not",
        r"could not be decrypted",
        r"encrypted content for item",
    )
)


@dataclass(frozen=True)
class _SuiteCheckpointContext:
    output_path: Path
    ordered_task_dirs: list[Path]
    retained_runs: dict[str, dict[str, Any]]
    config: AgentRunConfig
    agent_config_summary: dict[str, Any] | None
    worker_count: int
    retry_rate_limit: int
    retry_transient_api: int
    retry_only_statuses: frozenset[str]
    extra_agent_passes: int
    max_task_attempts: int | None
    eval_docker: bool
    eval_docker_image: str
    agent_docker: bool
    agent_docker_image: str
    resume_enabled: bool
    suite_source_dir: Path | None
    skipped_max_attempts: frozenset[str]
    runnable_count: int


def run_agent_on_path(
    input_path: str | Path,
    output_dir: str | Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None = None,
    num_workers: int = 1,
    progress: bool = False,
    *,
    task_ids: list[str] | None = None,
    skip_completed_dir: str | Path | None = None,
    retry_rate_limit: int = 1,
    retry_transient_api: int = 3,
    resume_dir: str | Path | None = None,
    resume_mode: bool = False,
    retry_only_statuses: frozenset[str] | None = None,
    extra_agent_passes: int = 0,
    max_task_attempts: int | None = None,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> dict[str, Any]:
    """Run an agent on one task directory or every task under a dataset root."""

    resolved = resolve_task_input(input_path)
    task_dirs = discover_task_dirs(resolved, task_ids=task_ids)
    output_path = Path(output_dir).resolve()
    if len(task_dirs) == 1 and (resolved / "metadata.json").is_file():
        return run_agent_on_task(
            task_dirs[0],
            output_path,
            config,
            agent_config_summary=agent_config_summary,
            progress=progress,
            eval_docker=eval_docker,
            eval_docker_image=eval_docker_image,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )
    return run_agent_on_suite(
        task_dirs,
        output_path,
        config,
        agent_config_summary=agent_config_summary,
        num_workers=num_workers,
        progress=progress,
        skip_completed_dir=skip_completed_dir,
        retry_rate_limit=retry_rate_limit,
        retry_transient_api=retry_transient_api,
        resume_dir=resume_dir,
        resume_mode=resume_mode,
        retry_only_statuses=retry_only_statuses or DEFAULT_RETRY_ONLY_STATUSES,
        extra_agent_passes=extra_agent_passes,
        max_task_attempts=max_task_attempts,
        eval_docker=eval_docker,
        eval_docker_image=eval_docker_image,
        agent_docker=agent_docker,
        agent_docker_image=agent_docker_image,
    )


def run_agent_on_suite(
    task_dirs: list[Path],
    output_dir: str | Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None = None,
    num_workers: int = 1,
    progress: bool = False,
    skip_completed_dir: str | Path | None = None,
    retry_rate_limit: int = 1,
    retry_transient_api: int = 3,
    resume_dir: str | Path | None = None,
    resume_mode: bool = False,
    retry_only_statuses: frozenset[str] = DEFAULT_RETRY_ONLY_STATUSES,
    extra_agent_passes: int = 0,
    max_task_attempts: int | None = None,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> dict[str, Any]:
    """Run an agent on multiple tasks and write a suite summary."""

    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    worker_count = max(1, int(num_workers))
    extra_passes = max(0, int(extra_agent_passes))

    suite_source_dir = _resolve_suite_source_dir(
        output_path=output_path,
        resume_dir=resume_dir,
        resume_mode=resume_mode,
        skip_completed_dir=skip_completed_dir,
    )
    use_resume_retain = resume_mode or resume_dir is not None
    retain_statuses = _resolve_retain_statuses(
        resume_mode=use_resume_retain,
        skip_completed_dir=skip_completed_dir if not use_resume_retain else None,
        retry_only_statuses=retry_only_statuses,
    )
    retained_runs = load_retained_runs(suite_source_dir, retain_statuses=retain_statuses)
    _validate_retained_runs(
        retained_runs,
        task_dirs=task_dirs,
        config=config,
        agent_docker=agent_docker,
        agent_docker_image=agent_docker_image,
        eval_docker=eval_docker,
        eval_docker_image=eval_docker_image,
    )
    skipped_max_attempts = _tasks_at_max_attempts(
        task_dirs,
        output_path,
        max_task_attempts,
        exclude_task_ids=set(retained_runs),
    )
    retained_runs = _merge_retained_runs(
        retained_runs,
        _load_existing_runs(output_path, skipped_max_attempts),
    )
    runnable_dirs = [
        task_dir
        for task_dir in task_dirs
        if task_dir.name not in retained_runs and task_dir.name not in skipped_max_attempts
    ]

    checkpoint_ctx = _SuiteCheckpointContext(
        output_path=output_path,
        ordered_task_dirs=task_dirs,
        retained_runs=retained_runs,
        config=config,
        agent_config_summary=agent_config_summary,
        worker_count=worker_count,
        retry_rate_limit=max(1, int(retry_rate_limit)),
        retry_transient_api=max(1, int(retry_transient_api)),
        retry_only_statuses=retry_only_statuses,
        extra_agent_passes=extra_passes,
        max_task_attempts=max_task_attempts,
        eval_docker=eval_docker,
        eval_docker_image=eval_docker_image,
        agent_docker=agent_docker,
        agent_docker_image=agent_docker_image,
        resume_enabled=use_resume_retain or skip_completed_dir is not None,
        suite_source_dir=suite_source_dir,
        skipped_max_attempts=frozenset(skipped_max_attempts),
        runnable_count=len(runnable_dirs),
    )

    runs = _run_suite_tasks(
        task_dirs=runnable_dirs,
        output_path=output_path,
        config=config,
        agent_config_summary=agent_config_summary,
        num_workers=worker_count,
        progress=progress,
        retry_rate_limit=max(1, int(retry_rate_limit)),
        retry_transient_api=max(1, int(retry_transient_api)),
        eval_docker=eval_docker,
        eval_docker_image=eval_docker_image,
        agent_docker=agent_docker,
        agent_docker_image=agent_docker_image,
        checkpoint_ctx=checkpoint_ctx,
    )

    if retained_runs:
        runs = _merge_suite_runs(task_dirs, runs, retained_runs)

    for pass_index in range(extra_passes):
        runs_by_id = {
            run.get("task_id"): run for run in runs if isinstance(run.get("task_id"), str)
        }
        retry_dirs = [
            task_dir
            for task_dir in task_dirs
            if runs_by_id.get(task_dir.name, {}).get("status") in retry_only_statuses
            and task_dir.name not in skipped_max_attempts
            and not _task_at_max_attempts(output_path / task_dir.name, max_task_attempts)
        ]
        if not retry_dirs:
            break
        retained = {
            task_id: run
            for task_id, run in runs_by_id.items()
            if run.get("status") not in retry_only_statuses
        }
        fresh_runs = _run_suite_tasks(
            task_dirs=retry_dirs,
            output_path=output_path,
            config=config,
            agent_config_summary=agent_config_summary,
            num_workers=worker_count,
            progress=progress,
            retry_rate_limit=max(1, int(retry_rate_limit)),
            retry_transient_api=max(1, int(retry_transient_api)),
            eval_docker=eval_docker,
            eval_docker_image=eval_docker_image,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )
        runs = _merge_suite_runs(task_dirs, fresh_runs, retained)
        snapshot_path = output_path / f"suite.pass{pass_index + 1}.json"
        _write_suite_snapshot(
            snapshot_path,
            runs=runs,
            config=config,
            agent_config_summary=agent_config_summary,
            output_path=output_path,
            worker_count=worker_count,
            retry_rate_limit=max(1, int(retry_rate_limit)),
            retry_transient_api=max(1, int(retry_transient_api)),
            retry_only_statuses=retry_only_statuses,
            extra_agent_passes=extra_passes,
            pass_index=pass_index + 1,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )

    summary = rebuild_suite_summary(runs)
    agent_usage_totals = _sum_agent_usage(runs)
    result = {
        "mode": "suite",
        "generated_at": _utc_now(),
        "agent": config.agent,
        "agent_config": agent_config_summary or {},
        "output_dir": str(output_path),
        "num_workers": worker_count,
        "agent_backend": "docker" if agent_docker else "local",
        "agent_docker_image": agent_docker_image if agent_docker else "",
        "eval_backend": "docker" if eval_docker else "local",
        "eval_docker_image": eval_docker_image if eval_docker else "",
        "retry_rate_limit": max(1, int(retry_rate_limit)),
        "retry_transient_api": max(1, int(retry_transient_api)),
        "retry_only_statuses": sorted(retry_only_statuses),
        "extra_agent_passes": extra_passes,
        "max_task_attempts": max_task_attempts,
        "skipped_completed": sorted(retained_runs),
        "resume": {
            "enabled": resume_mode or resume_dir is not None or skip_completed_dir is not None,
            "source_dir": str(suite_source_dir) if suite_source_dir is not None else "",
            "retained": len(retained_runs),
            "retried": len(runnable_dirs),
            "skipped_max_attempts": sorted(skipped_max_attempts),
        },
        "summary": summary,
        "agent_usage_totals": agent_usage_totals,
        "runs": [compact_suite_run_entry(run) for run in runs],
    }
    (output_path / "suite.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def run_agent_on_task(
    task_dir: str | Path,
    output_dir: str | Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None = None,
    progress: bool = False,
    *,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> dict[str, Any]:
    """Run an agent on a single task, collect its submission, and evaluate it."""

    task_path = Path(task_dir).resolve()
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    if progress and sys.stderr.isatty():
        task_id = task_path.name
        with live_suite_progress(
            num_tasks=1,
            output_dir=output_path,
            agent=config.agent,
            layout="flat",
        ) as progress_manager:
            progress_manager.on_task_start(task_id)
            progress_manager.update_task_status(task_id, "running")
            try:
                result = run_agent_on_task(
                    task_path,
                    output_path,
                    config,
                    agent_config_summary=agent_config_summary,
                    progress=False,
                    eval_docker=eval_docker,
                    eval_docker_image=eval_docker_image,
                    agent_docker=agent_docker,
                    agent_docker_image=agent_docker_image,
                )
            except BaseException:
                progress_manager.on_task_end(task_id, "error")
                raise
            progress_manager.update_task_status(task_id, str(result.get("status", "finished")))
            progress_manager.on_task_end(task_id, str(result.get("status", "unknown")))
            return result

    next_attempt, previous_attempt_json = _archive_previous_run(output_path)

    workspace_dir = output_path / "workspace"
    agent_output_dir = output_path / "agent"
    collected_submission_dir = output_path / "submission"
    eval_output_dir = output_path / "eval"
    for path in (workspace_dir, agent_output_dir, collected_submission_dir, eval_output_dir):
        _reset_dir(path)

    errors: list[str] = []
    ablation = ablation_options_from_env(config.env)
    validation = validate_runnable_task(task_path)
    task_id = validation.task_id
    metadata: dict[str, Any] = {}
    source_provenance: dict[str, Any] | None = None
    freeze_provenance: dict[str, Any] | None = None
    if not validation.valid:
        errors.extend(f"invalid task: {error}" for error in validation.errors)
    else:
        metadata = load_metadata(task_path).data
        task_id = metadata.get("task_id", task_id)
        source_provenance = (
            pruned_source_provenance(str(task_id))
            if ablation.source_context == "pruned_context"
            else source_provenance_for_task(str(task_id))
        )
        freeze_provenance = benchmark_freeze_provenance(
            str(task_id),
            require=_is_python_main_task(task_path),
        )
        if freeze_provenance is not None:
            if freeze_provenance.get("spec_hash") != metadata.get("spec_hash"):
                raise ValueError(f"{task_id}: active benchmark freeze spec hash mismatch")
            if (
                ablation.source_context == "full_repository"
                and (
                    source_provenance is None
                    or freeze_provenance.get("source_snapshot_id")
                    != source_provenance.get("source_snapshot_id")
                    or freeze_provenance.get("source_tree_sha256")
                    != source_provenance.get("source_digest")
                )
            ):
                raise ValueError(f"{task_id}: active benchmark freeze source mismatch")

    agent_result = None
    eval_result = None
    recovery_info: dict[str, Any] | None = None
    repo_graph_state: RepoGraphRunState | None = None
    repo_graph_usage: dict[str, Any] | None = None
    contract_closure_audit: dict[str, Any] | None = None
    adaptive_budget_v2_audit: dict[str, Any] | None = None
    pre_agent_failure = False
    workspace_submission_dir = workspace_dir / "submission"
    stdout_log = agent_output_dir / "stdout.log"
    stderr_log = agent_output_dir / "stderr.log"

    if validation.valid:
        silent_finish = (config.env or {}).get(LITE_V1_SILENT_FINISH_ENV, "").strip()
        if silent_finish:
            os.environ[LITE_V1_SILENT_FINISH_ENV] = silent_finish
        task_file = prepare_agent_workspace(
            task_path,
            workspace_dir,
            metadata,
            ablation=ablation,
        )
        if records_source_ablation(ablation, config.env):
            write_visible_workspace_inventory(
                workspace_dir,
                agent_output_dir,
                options=ablation,
                extra={"task_id": str(task_id)},
            )
        run_config = config
        agent_ready = True
        try:
            repo_graph_policy = RepoGraphPolicy.from_env(config.env)
        except ValueError as exc:
            errors.append(f"repository graph configuration failed before agent start: {exc}")
            repo_graph_policy = None
            agent_ready = False
            pre_agent_failure = True
        if repo_graph_policy is not None and repo_graph_policy.enabled:
            try:
                repo_graph_state = initialize_repo_graph(
                    workspace_dir=workspace_dir,
                    agent_output_dir=agent_output_dir,
                    config_env=config.env,
                )
                assert repo_graph_state is not None
                append_repo_graph_prompt(task_file, repo_graph_state)
                run_config = replace(
                    config,
                    env={**(config.env or {}), **repo_graph_state.env},
                )
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                _write_repo_graph_initialization_failure(
                    agent_output_dir,
                    policy=repo_graph_policy,
                    error=exc,
                )
                errors.append(f"repository graph initialization failed before agent start: {exc}")
                agent_ready = not repo_graph_policy.fail_fast
                pre_agent_failure = repo_graph_policy.fail_fast
        prompt_path = agent_output_dir / "prompt.txt"
        prompt_path.write_text(task_file.read_text(encoding="utf-8"), encoding="utf-8")

        context = AgentRunContext(
            workspace_dir=workspace_dir,
            task_file=task_file,
            submission_dir=workspace_submission_dir,
            agent_output_dir=agent_output_dir,
            task_text=task_file.read_text(encoding="utf-8"),
        )
        phase1_agent_result = None
        phase1_gate = None
        if agent_ready and ablation.td_cognition:
            from .td_cognition import TD_PHASE_ENV
            from .td_cognition import evaluate_phase1_artifacts
            from .td_cognition import prepare_phase2_workspace
            from .td_cognition import write_phase_audit

            phase1_dir = output_path / "agent_phase1"
            _reset_dir(phase1_dir)
            phase1_timeout = min(int(run_config.timeout_seconds or 3600), 1800)
            phase1_config = replace(
                run_config,
                timeout_seconds=phase1_timeout,
                env={
                    **(run_config.env or {}),
                    TD_PHASE_ENV: "cognition",
                    "FEATURELIFTBENCH_TD_COGNITION": "1",
                },
            )
            phase1_context = AgentRunContext(
                workspace_dir=workspace_dir,
                task_file=task_file,
                submission_dir=workspace_submission_dir,
                agent_output_dir=phase1_dir,
                task_text=task_file.read_text(encoding="utf-8"),
            )
            phase1_stdout = phase1_dir / "stdout.log"
            phase1_stderr = phase1_dir / "stderr.log"
            try:
                if agent_docker:
                    phase1_agent_result = run_agent_in_docker(
                        phase1_context,
                        phase1_config,
                        image=agent_docker_image,
                        stdout_log=phase1_stdout,
                        stderr_log=phase1_stderr,
                    )
                else:
                    adapter = get_agent_adapter(phase1_config.agent)
                    phase1_agent_result = adapter.run(
                        phase1_context,
                        phase1_config,
                        stdout_log=phase1_stdout,
                        stderr_log=phase1_stderr,
                    )
            except ValueError as exc:
                errors.append(f"td_cognition phase1 failed: {exc}")
            if phase1_agent_result is not None and not phase1_stdout.is_file():
                _write_agent_logs(phase1_dir, phase1_agent_result)

            phase1_gate = evaluate_phase1_artifacts(
                workspace_dir,
                run_pytest=True,
                pytest_backend="docker" if agent_docker else "local",
                docker_image=agent_docker_image if agent_docker else None,
            )
            # Phase 2 always proceeds; incomplete cognition is recorded.
            phase2_task_text = prepare_phase2_workspace(
                workspace_dir,
                task_file.read_text(encoding="utf-8"),
            )
            task_file = workspace_dir / "TASK.md"
            prompt_path.write_text(phase2_task_text, encoding="utf-8")
            _reset_dir(agent_output_dir)
            phase2_config = replace(
                run_config,
                env={
                    **(run_config.env or {}),
                    TD_PHASE_ENV: "implement",
                    "FEATURELIFTBENCH_TD_COGNITION": "1",
                },
            )
            context = AgentRunContext(
                workspace_dir=workspace_dir,
                task_file=task_file,
                submission_dir=workspace_submission_dir,
                agent_output_dir=agent_output_dir,
                task_text=phase2_task_text,
            )
            stdout_log = agent_output_dir / "stdout.log"
            stderr_log = agent_output_dir / "stderr.log"
            try:
                if agent_docker:
                    agent_result = run_agent_in_docker(
                        context,
                        phase2_config,
                        image=agent_docker_image,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
                else:
                    adapter = get_agent_adapter(phase2_config.agent)
                    agent_result = adapter.run(
                        context,
                        phase2_config,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
            except ValueError as exc:
                errors.append(f"td_cognition phase2 failed: {exc}")
            write_phase_audit(
                output_path,
                phase1_result=phase1_gate,
                phase1_agent=(
                    None
                    if phase1_agent_result is None
                    else {
                        "name": phase1_agent_result.name,
                        "passed": phase1_agent_result.passed,
                        "returncode": phase1_agent_result.returncode,
                        "duration_seconds": phase1_agent_result.duration_seconds,
                        "timed_out": phase1_agent_result.timed_out,
                        "reason": phase1_agent_result.reason,
                        "resource_limited": phase1_agent_result.resource_limited,
                    }
                ),
                phase2_agent=(
                    None
                    if agent_result is None
                    else {
                        "name": agent_result.name,
                        "passed": agent_result.passed,
                        "returncode": agent_result.returncode,
                        "duration_seconds": agent_result.duration_seconds,
                        "timed_out": agent_result.timed_out,
                        "reason": agent_result.reason,
                        "resource_limited": agent_result.resource_limited,
                    }
                ),
            )
            if not phase1_gate.ok:
                errors.append(
                    "td_cognition phase1 cognition incomplete: "
                    + "; ".join(phase1_gate.errors)
                )
        elif agent_ready and ablation.exec_contract:
            from .exec_contract import collect_upstream_runtime
            from .exec_contract import compute_evidence_gate_ok
            from .exec_contract import deactivate_exec_contract_workspace
            from .exec_contract import phase1_task_appendix as exec_phase1_appendix
            from .exec_contract import prepare_repair_workspace
            from .exec_contract import synthesize_contracts
            from .exec_contract import verify_submission_contracts
            from .exec_contract import write_exec_contract_audit
            from .exec_contract.common import DEFAULT_REPAIR_ROUNDS
            from .exec_contract.common import DEFAULT_REPAIR_TIMEOUT_SECONDS

            public_spec = metadata.get("public_spec") if isinstance(metadata.get("public_spec"), dict) else {}
            collect_meta = collect_upstream_runtime(
                workspace_dir,
                public_spec,
                docker_image=agent_docker_image if agent_docker else None,
                use_docker=bool(agent_docker),
            )
            synthesize_meta = synthesize_contracts(
                workspace_dir,
                public_spec,
                collect_meta=collect_meta,
                variant=ablation.exec_contract_variant,
            )
            fallback_to_main = (
                ablation.exec_contract_variant == "fcec"
                and not compute_evidence_gate_ok(
                    collect_meta=collect_meta,
                    synthesize_meta=synthesize_meta,
                )
            )
            # Refresh TASK appendix now that RUNTIME_FACTS exists.
            base_task = task_file.read_text(encoding="utf-8")
            import re as _re
            base_task = _re.sub(
                r"\n## Execution-Guided Contract.*",
                "",
                base_task,
                flags=_re.DOTALL,
            ).rstrip()
            if fallback_to_main:
                # The evidence doctor failed. Remove all method-only artifacts
                # so the single implementation call is a byte-for-byte Main
                # information condition rather than a weakly labeled capsule.
                deactivate_exec_contract_workspace(workspace_dir)
                refreshed = base_task
            else:
                refreshed = (
                    base_task
                    + "\n\n## Execution-Guided Contract\n\n"
                    + exec_phase1_appendix(
                        variant=ablation.exec_contract_variant
                    )
                )
            task_file.write_text(refreshed + "\n", encoding="utf-8")
            prompt_path.write_text(refreshed, encoding="utf-8")
            context = AgentRunContext(
                workspace_dir=workspace_dir,
                task_file=task_file,
                submission_dir=workspace_submission_dir,
                agent_output_dir=agent_output_dir,
                task_text=refreshed,
            )
            exec_env = dict(run_config.env or {})
            if fallback_to_main:
                exec_env.pop("FEATURELIFTBENCH_EXEC_CONTRACT", None)
                exec_env.pop("FEATURELIFTBENCH_EXEC_CONTRACT_PHASE", None)
            else:
                exec_env.update(
                    {
                        "FEATURELIFTBENCH_EXEC_CONTRACT": "1",
                        "FEATURELIFTBENCH_EXEC_CONTRACT_PHASE": "implement",
                    }
                )
            primary_config = replace(run_config, env=exec_env)
            try:
                if agent_docker:
                    agent_result = run_agent_in_docker(
                        context,
                        primary_config,
                        image=agent_docker_image,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
                else:
                    adapter = get_agent_adapter(primary_config.agent)
                    agent_result = adapter.run(
                        context,
                        primary_config,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
            except ValueError as exc:
                errors.append(f"exec_contract implement failed: {exc}")

            verify_initial = (
                {
                    "ok": False,
                    "skipped": True,
                    "reason": "fail-closed Main fallback",
                }
                if fallback_to_main
                else verify_submission_contracts(
                    workspace_dir,
                    docker_image=agent_docker_image if agent_docker else None,
                    use_docker=bool(agent_docker),
                )
            )
            verify_final = verify_initial
            repair_agent_result = None
            repair_rounds_used = 0
            if (
                not fallback_to_main
                and not verify_initial.get("ok")
                and DEFAULT_REPAIR_ROUNDS > 0
            ):
                repair_rounds_used = 1
                repair_task = prepare_repair_workspace(
                    workspace_dir,
                    verify_result=verify_initial,
                    task_markdown=task_file.read_text(encoding="utf-8"),
                )
                prompt_path.write_text(repair_task, encoding="utf-8")
                repair_dir = output_path / "agent_repair"
                _reset_dir(repair_dir)
                repair_stdout = repair_dir / "stdout.log"
                repair_stderr = repair_dir / "stderr.log"
                repair_config = replace(
                    run_config,
                    timeout_seconds=min(
                        int(run_config.timeout_seconds or 3600),
                        DEFAULT_REPAIR_TIMEOUT_SECONDS,
                    ),
                    env={
                        **(run_config.env or {}),
                        "FEATURELIFTBENCH_EXEC_CONTRACT": "1",
                        "FEATURELIFTBENCH_EXEC_CONTRACT_PHASE": "repair",
                    },
                )
                repair_context = AgentRunContext(
                    workspace_dir=workspace_dir,
                    task_file=task_file,
                    submission_dir=workspace_submission_dir,
                    agent_output_dir=repair_dir,
                    task_text=repair_task,
                )
                try:
                    if agent_docker:
                        repair_agent_result = run_agent_in_docker(
                            repair_context,
                            repair_config,
                            image=agent_docker_image,
                            stdout_log=repair_stdout,
                            stderr_log=repair_stderr,
                        )
                    else:
                        adapter = get_agent_adapter(repair_config.agent)
                        repair_agent_result = adapter.run(
                            repair_context,
                            repair_config,
                            stdout_log=repair_stdout,
                            stderr_log=repair_stderr,
                        )
                except ValueError as exc:
                    errors.append(f"exec_contract repair failed: {exc}")
                verify_final = verify_submission_contracts(
                    workspace_dir,
                    docker_image=agent_docker_image if agent_docker else None,
                    use_docker=bool(agent_docker),
                )

            write_exec_contract_audit(
                output_path,
                variant=ablation.exec_contract_variant,
                collect_meta=collect_meta,
                synthesize_meta=synthesize_meta,
                verify_initial=verify_initial,
                verify_final=verify_final,
                repair_rounds_used=repair_rounds_used,
                agent_primary=(
                    None
                    if agent_result is None
                    else {
                        "name": agent_result.name,
                        "passed": agent_result.passed,
                        "returncode": agent_result.returncode,
                        "duration_seconds": agent_result.duration_seconds,
                        "timed_out": agent_result.timed_out,
                        "reason": agent_result.reason,
                        "resource_limited": agent_result.resource_limited,
                    }
                ),
                agent_repair=(
                    None
                    if repair_agent_result is None
                    else {
                        "name": repair_agent_result.name,
                        "passed": repair_agent_result.passed,
                        "returncode": repair_agent_result.returncode,
                        "duration_seconds": repair_agent_result.duration_seconds,
                        "timed_out": repair_agent_result.timed_out,
                        "reason": repair_agent_result.reason,
                        "resource_limited": repair_agent_result.resource_limited,
                    }
                ),
                fallback_to_main=fallback_to_main,
            )
            if not fallback_to_main and not verify_final.get("ok"):
                errors.append(
                    "exec_contract contracts incomplete: "
                    + str(verify_final.get("error") or verify_final.get("stderr_tail") or "contracts failed")[:500]
                )
        elif agent_ready and ablation.self_contract:
            import re as _re

            from .exec_contract import collect_upstream_runtime
            from .exec_contract import verify_submission_contracts
            from .self_contract import author_task_appendix
            from .self_contract import evaluate_author_gate
            from .self_contract import freeze_contracts
            from .self_contract import implement_task_appendix
            from .self_contract import prepare_author_repair_workspace
            from .self_contract import prepare_impl_repair_workspace
            from .self_contract import reset_submission_dir
            from .self_contract import verify_contracts_frozen
            from .self_contract import write_self_contract_audit
            from .self_contract.common import DEFAULT_AUTHOR_REPAIR_ROUNDS
            from .self_contract.common import DEFAULT_AUTHOR_TIMEOUT_SECONDS
            from .self_contract.common import DEFAULT_IMPL_REPAIR_ROUNDS
            from .self_contract.common import DEFAULT_REPAIR_TIMEOUT_SECONDS
            from .self_contract.common import SELF_CONTRACT_ENV
            from .self_contract.common import SELF_CONTRACT_PHASE_ENV

            def _agent_compact(result: Any) -> dict[str, Any] | None:
                if result is None:
                    return None
                return {
                    "name": result.name,
                    "passed": result.passed,
                    "returncode": result.returncode,
                    "duration_seconds": result.duration_seconds,
                    "timed_out": result.timed_out,
                    "reason": result.reason,
                    "resource_limited": result.resource_limited,
                }

            public_spec = (
                metadata.get("public_spec")
                if isinstance(metadata.get("public_spec"), dict)
                else {}
            )
            # Phase 0: facts only (no harness-synthesized contracts).
            collect_meta = collect_upstream_runtime(
                workspace_dir,
                public_spec,
                docker_image=agent_docker_image if agent_docker else None,
                use_docker=bool(agent_docker),
            )

            def _refresh_task(section_title: str, appendix: str) -> str:
                base = task_file.read_text(encoding="utf-8")
                base = _re.sub(
                    r"\n## Self-Authored Contract.*",
                    "",
                    base,
                    flags=_re.DOTALL,
                ).rstrip()
                refreshed = base + f"\n\n## {section_title}\n\n" + appendix
                task_file.write_text(refreshed + "\n", encoding="utf-8")
                prompt_path.write_text(refreshed, encoding="utf-8")
                return refreshed

            # Phase A — author contracts
            author_text = _refresh_task(
                "Self-Authored Contract Phase A", author_task_appendix()
            )
            author_dir = output_path / "agent_author"
            _reset_dir(author_dir)
            author_stdout = author_dir / "stdout.log"
            author_stderr = author_dir / "stderr.log"
            author_timeout = min(
                int(run_config.timeout_seconds or 3600),
                DEFAULT_AUTHOR_TIMEOUT_SECONDS,
            )
            author_config = replace(
                run_config,
                timeout_seconds=author_timeout,
                env={
                    **(run_config.env or {}),
                    SELF_CONTRACT_ENV: "1",
                    SELF_CONTRACT_PHASE_ENV: "author",
                },
            )
            author_context = AgentRunContext(
                workspace_dir=workspace_dir,
                task_file=task_file,
                submission_dir=workspace_submission_dir,
                agent_output_dir=author_dir,
                task_text=author_text,
            )
            author_agent_result = None
            try:
                if agent_docker:
                    author_agent_result = run_agent_in_docker(
                        author_context,
                        author_config,
                        image=agent_docker_image,
                        stdout_log=author_stdout,
                        stderr_log=author_stderr,
                    )
                else:
                    adapter = get_agent_adapter(author_config.agent)
                    author_agent_result = adapter.run(
                        author_context,
                        author_config,
                        stdout_log=author_stdout,
                        stderr_log=author_stderr,
                    )
            except ValueError as exc:
                errors.append(f"self_contract author failed: {exc}")

            author_gate = evaluate_author_gate(
                workspace_dir,
                docker_image=agent_docker_image if agent_docker else None,
                use_docker=bool(agent_docker),
            )
            author_repair_rounds = 0
            if (
                not author_gate.get("ok")
                and DEFAULT_AUTHOR_REPAIR_ROUNDS > 0
            ):
                author_repair_rounds = 1
                repair_text = prepare_author_repair_workspace(
                    workspace_dir,
                    gate_result=author_gate,
                    task_markdown=task_file.read_text(encoding="utf-8"),
                )
                prompt_path.write_text(repair_text, encoding="utf-8")
                author_repair_dir = output_path / "agent_author_repair"
                _reset_dir(author_repair_dir)
                author_repair_stdout = author_repair_dir / "stdout.log"
                author_repair_stderr = author_repair_dir / "stderr.log"
                author_repair_config = replace(
                    run_config,
                    timeout_seconds=min(
                        int(run_config.timeout_seconds or 3600),
                        DEFAULT_REPAIR_TIMEOUT_SECONDS,
                    ),
                    env={
                        **(run_config.env or {}),
                        SELF_CONTRACT_ENV: "1",
                        SELF_CONTRACT_PHASE_ENV: "author_repair",
                    },
                )
                author_repair_context = AgentRunContext(
                    workspace_dir=workspace_dir,
                    task_file=task_file,
                    submission_dir=workspace_submission_dir,
                    agent_output_dir=author_repair_dir,
                    task_text=repair_text,
                )
                try:
                    if agent_docker:
                        author_agent_result = run_agent_in_docker(
                            author_repair_context,
                            author_repair_config,
                            image=agent_docker_image,
                            stdout_log=author_repair_stdout,
                            stderr_log=author_repair_stderr,
                        )
                    else:
                        adapter = get_agent_adapter(author_repair_config.agent)
                        author_agent_result = adapter.run(
                            author_repair_context,
                            author_repair_config,
                            stdout_log=author_repair_stdout,
                            stderr_log=author_repair_stderr,
                        )
                except ValueError as exc:
                    errors.append(f"self_contract author repair failed: {exc}")
                author_gate = evaluate_author_gate(
                    workspace_dir,
                    docker_image=agent_docker_image if agent_docker else None,
                    use_docker=bool(agent_docker),
                )

            freeze_meta: dict[str, Any] | None = None
            freeze_check: dict[str, Any] | None = None
            verify_initial: dict[str, Any] | None = None
            verify_final: dict[str, Any] | None = None
            impl_repair_rounds = 0
            repair_agent_result = None

            if not author_gate.get("ok"):
                errors.append(
                    "self_contract author gate failed: "
                    + "; ".join(str(e) for e in (author_gate.get("errors") or []))[:500]
                )
            else:
                freeze_meta = freeze_contracts(workspace_dir)
                reset_submission_dir(workspace_dir)
                impl_text = _refresh_task(
                    "Self-Authored Contract Phase B",
                    implement_task_appendix(),
                )
                _reset_dir(agent_output_dir)
                stdout_log = agent_output_dir / "stdout.log"
                stderr_log = agent_output_dir / "stderr.log"
                impl_config = replace(
                    run_config,
                    env={
                        **(run_config.env or {}),
                        SELF_CONTRACT_ENV: "1",
                        SELF_CONTRACT_PHASE_ENV: "implement",
                    },
                )
                context = AgentRunContext(
                    workspace_dir=workspace_dir,
                    task_file=task_file,
                    submission_dir=workspace_submission_dir,
                    agent_output_dir=agent_output_dir,
                    task_text=impl_text,
                )
                try:
                    if agent_docker:
                        agent_result = run_agent_in_docker(
                            context,
                            impl_config,
                            image=agent_docker_image,
                            stdout_log=stdout_log,
                            stderr_log=stderr_log,
                        )
                    else:
                        adapter = get_agent_adapter(impl_config.agent)
                        agent_result = adapter.run(
                            context,
                            impl_config,
                            stdout_log=stdout_log,
                            stderr_log=stderr_log,
                        )
                except ValueError as exc:
                    errors.append(f"self_contract implement failed: {exc}")

                verify_initial = verify_submission_contracts(
                    workspace_dir,
                    docker_image=agent_docker_image if agent_docker else None,
                    use_docker=bool(agent_docker),
                )
                verify_final = verify_initial
                if (
                    not verify_initial.get("ok")
                    and DEFAULT_IMPL_REPAIR_ROUNDS > 0
                ):
                    impl_repair_rounds = 1
                    repair_task = prepare_impl_repair_workspace(
                        workspace_dir,
                        verify_result=verify_initial,
                        task_markdown=task_file.read_text(encoding="utf-8"),
                    )
                    prompt_path.write_text(repair_task, encoding="utf-8")
                    repair_dir = output_path / "agent_repair"
                    _reset_dir(repair_dir)
                    repair_stdout = repair_dir / "stdout.log"
                    repair_stderr = repair_dir / "stderr.log"
                    repair_config = replace(
                        run_config,
                        timeout_seconds=min(
                            int(run_config.timeout_seconds or 3600),
                            DEFAULT_REPAIR_TIMEOUT_SECONDS,
                        ),
                        env={
                            **(run_config.env or {}),
                            SELF_CONTRACT_ENV: "1",
                            SELF_CONTRACT_PHASE_ENV: "repair",
                        },
                    )
                    repair_context = AgentRunContext(
                        workspace_dir=workspace_dir,
                        task_file=task_file,
                        submission_dir=workspace_submission_dir,
                        agent_output_dir=repair_dir,
                        task_text=repair_task,
                    )
                    try:
                        if agent_docker:
                            repair_agent_result = run_agent_in_docker(
                                repair_context,
                                repair_config,
                                image=agent_docker_image,
                                stdout_log=repair_stdout,
                                stderr_log=repair_stderr,
                            )
                        else:
                            adapter = get_agent_adapter(repair_config.agent)
                            repair_agent_result = adapter.run(
                                repair_context,
                                repair_config,
                                stdout_log=repair_stdout,
                                stderr_log=repair_stderr,
                            )
                    except ValueError as exc:
                        errors.append(f"self_contract repair failed: {exc}")
                    verify_final = verify_submission_contracts(
                        workspace_dir,
                        docker_image=agent_docker_image if agent_docker else None,
                        use_docker=bool(agent_docker),
                    )

                freeze_check = verify_contracts_frozen(workspace_dir)
                if not freeze_check.get("ok"):
                    errors.append(
                        "self_contract freeze check failed: "
                        + str(freeze_check.get("error") or "lock mismatch")[:500]
                    )
                if not (verify_final or {}).get("ok"):
                    errors.append(
                        "self_contract contracts incomplete: "
                        + str(
                            (verify_final or {}).get("error")
                            or (verify_final or {}).get("stderr_tail")
                            or "contracts failed"
                        )[:500]
                    )

            write_self_contract_audit(
                output_path,
                collect_meta=collect_meta,
                author_gate=author_gate,
                freeze_meta=freeze_meta,
                freeze_check=freeze_check,
                verify_initial=verify_initial,
                verify_final=verify_final,
                author_repair_rounds=author_repair_rounds,
                impl_repair_rounds=impl_repair_rounds,
                agent_author=_agent_compact(author_agent_result),
                agent_implement=_agent_compact(agent_result),
                agent_repair=_agent_compact(repair_agent_result),
            )
        elif agent_ready and ablation.contract_closure_budget_control:
            from .contract_closure_budget_control import CONTROL_PHASE_ENV
            from .contract_closure_budget_control import DEFAULT_PRIMARY_MAX_STEPS
            from .contract_closure_budget_control import DEFAULT_PRIMARY_TOKEN_LIMIT
            from .llm_usage_proxy import TOTAL_TOKEN_LIMIT_ENV

            control_env = dict(run_config.env or {})
            control_env[CONTROL_PHASE_ENV] = "primary"
            control_env.setdefault(
                "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS",
                str(DEFAULT_PRIMARY_MAX_STEPS),
            )
            control_env.setdefault(
                TOTAL_TOKEN_LIMIT_ENV,
                str(DEFAULT_PRIMARY_TOKEN_LIMIT),
            )
            control_config = replace(run_config, env=control_env)
            try:
                if agent_docker:
                    agent_result = run_agent_in_docker(
                        context,
                        control_config,
                        image=agent_docker_image,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
                else:
                    adapter = get_agent_adapter(control_config.agent)
                    agent_result = adapter.run(
                        context,
                        control_config,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
            except ValueError as exc:
                errors.append(f"contract_closure_budget_control run failed: {exc}")
        elif agent_ready and (
            ablation.contract_closure_gate
            or ablation.contract_closure_gate_lite
            or ablation.contract_closure_gate_lite_v1
            or ablation.contract_closure_gate_lite_rescue
            or ablation.contract_closure_gate_lite_rescue_plus
            or ablation.contract_closure_gate_v3
        ):
            from .contract_closure_gate import check_workspace_isolated
            from .contract_closure_gate import decide_repair
            from .contract_closure_gate import prepare_repair_workspace
            from .contract_closure_gate import write_contract_closure_audit
            from .contract_closure_gate.common import CONTRACT_CLOSURE_GATE_ENV
            from .contract_closure_gate.common import CONTRACT_CLOSURE_GATE_LITE_ENV
            from .contract_closure_gate.common import (
                CONTRACT_CLOSURE_GATE_LITE_V1_ENV,
            )
            from .contract_closure_gate.common import (
                CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV,
            )
            from .contract_closure_gate.common import (
                CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV,
            )
            from .contract_closure_gate.common import CONTRACT_CLOSURE_GATE_V3_ENV
            from .contract_closure_gate.common import CONTRACT_CLOSURE_PHASE_ENV
            from .contract_closure_gate.common import DEFAULT_LITE_PRIMARY_MAX_STEPS
            from .contract_closure_gate.common import DEFAULT_LITE_PRIMARY_TOKEN_LIMIT
            from .contract_closure_gate.common import DEFAULT_LITE_INFRA_RETRY_LIMIT
            from .contract_closure_gate.common import (
                DEFAULT_LITE_INFRA_RETRY_MAX_TRIGGER_STEPS,
            )
            from .contract_closure_gate.common import DEFAULT_LITE_REPAIR_MAX_STEPS
            from .contract_closure_gate.common import DEFAULT_LITE_REPAIR_TOKEN_LIMIT
            from .contract_closure_gate.common import (
                DEFAULT_LITE_V1_REPAIR_MAX_STEPS,
            )
            from .contract_closure_gate.common import (
                DEFAULT_LITE_V1_REPAIR_TOKEN_LIMIT,
            )
            from .contract_closure_gate.common import DEFAULT_REPAIR_MAX_STEPS
            from .contract_closure_gate.common import DEFAULT_REPAIR_ROUNDS
            from .contract_closure_gate.common import DEFAULT_REPAIR_TIMEOUT_SECONDS
            from .contract_closure_gate.common import PRIMARY_MAX_STEPS_ENV
            from .contract_closure_gate.common import PRIMARY_TOKEN_LIMIT_ENV
            from .contract_closure_gate.common import REPAIR_MAX_STEPS_ENV
            from .contract_closure_gate.common import REPAIR_TOKEN_LIMIT_ENV
            from .contract_closure_gate.common import INFRA_RETRY_LIMIT_ENV
            from .contract_closure_gate.common import INFRA_RETRY_MAX_STEPS_ENV
            from .contract_closure_gate.common import LITE_POLICY_VERSION
            from .contract_closure_gate.common import LITE_RESCUE_POLICY_VERSION
            from .contract_closure_gate.common import (
                LITE_RESCUE_PLUS_POLICY_VERSION,
            )
            from .contract_closure_gate.common import LITE_V1_POLICY_VERSION
            from .llm_usage_proxy import TOTAL_TOKEN_LIMIT_ENV

            closure_v3 = ablation.contract_closure_gate_v3
            closure_v1 = ablation.contract_closure_gate_lite_v1
            closure_rescue = ablation.contract_closure_gate_lite_rescue
            closure_rescue_plus = (
                ablation.contract_closure_gate_lite_rescue_plus
            )
            closure_lite = (
                ablation.contract_closure_gate_lite
                or closure_v1
                or closure_rescue
                or closure_rescue_plus
                or closure_v3
            )
            closure_check_mode = (
                "lite_plus"
                if closure_rescue_plus
                else "micro"
                if closure_v3
                else "structure"
                if closure_lite
                else "full"
            )

            def _closure_agent_compact(result: Any, output_dir: Path) -> dict[str, Any] | None:
                if result is None:
                    return None
                return {
                    "name": result.name,
                    "passed": result.passed,
                    "returncode": result.returncode,
                    "duration_seconds": result.duration_seconds,
                    "timed_out": result.timed_out,
                    "reason": result.reason,
                    "resource_limited": result.resource_limited,
                    "usage": _collect_agent_usage(result.name, output_dir),
                }

            primary_env = dict(run_config.env or {})
            primary_env[CONTRACT_CLOSURE_PHASE_ENV] = "primary"
            primary_limit = _positive_env_int(
                primary_env,
                PRIMARY_TOKEN_LIMIT_ENV,
                default=(DEFAULT_LITE_PRIMARY_TOKEN_LIMIT if closure_lite else None),
            )
            if primary_limit is not None:
                primary_env[TOTAL_TOKEN_LIMIT_ENV] = str(primary_limit)
            primary_steps = _positive_env_int(
                primary_env,
                PRIMARY_MAX_STEPS_ENV,
                default=(DEFAULT_LITE_PRIMARY_MAX_STEPS if closure_lite else None),
            )
            if primary_steps is not None:
                primary_env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"] = str(primary_steps)
            primary_config = replace(run_config, env=primary_env)

            try:
                if agent_docker:
                    agent_result = run_agent_in_docker(
                        context,
                        primary_config,
                        image=agent_docker_image,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
                else:
                    adapter = get_agent_adapter(run_config.agent)
                    agent_result = adapter.run(
                        context,
                        primary_config,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
            except ValueError as exc:
                errors.append(f"contract_closure_gate primary run failed: {exc}")

            infrastructure_retry = _contract_closure_infrastructure_retry_decision(
                agent_result=agent_result,
                agent_output_dir=agent_output_dir,
                submission_dir=workspace_submission_dir,
                enabled=closure_lite,
                retry_limit=(
                    _positive_env_int(
                        primary_env,
                        INFRA_RETRY_LIMIT_ENV,
                        default=DEFAULT_LITE_INFRA_RETRY_LIMIT,
                    )
                    or 0
                ),
                max_trigger_steps=(
                    _positive_env_int(
                        primary_env,
                        INFRA_RETRY_MAX_STEPS_ENV,
                        default=DEFAULT_LITE_INFRA_RETRY_MAX_TRIGGER_STEPS,
                    )
                    or DEFAULT_LITE_INFRA_RETRY_MAX_TRIGGER_STEPS
                ),
                policy_version=(
                    LITE_V1_POLICY_VERSION
                    if closure_v1
                    else LITE_RESCUE_POLICY_VERSION
                    if closure_rescue
                    else LITE_RESCUE_PLUS_POLICY_VERSION
                    if closure_rescue_plus
                    else LITE_POLICY_VERSION
                ),
            )
            primary_attempts: list[dict[str, Any]] = []
            if agent_result is not None:
                primary_attempts.append(
                    _closure_agent_compact(agent_result, agent_output_dir) or {}
                )
            if infrastructure_retry.get("eligible"):
                first_attempt_dir = output_path / "agent_primary_attempt1"
                if first_attempt_dir.exists():
                    shutil.rmtree(first_attempt_dir)
                shutil.move(str(agent_output_dir), str(first_attempt_dir))
                agent_output_dir.mkdir(parents=True, exist_ok=True)
                prompt_path = agent_output_dir / "prompt.txt"
                prompt_path.write_text(
                    task_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
                stdout_log = agent_output_dir / "stdout.log"
                stderr_log = agent_output_dir / "stderr.log"
                # The eligible class requires an empty submission, but reset it
                # explicitly so a retry never inherits partial agent output.
                _reset_dir(workspace_submission_dir)
                retry_context = AgentRunContext(
                    workspace_dir=workspace_dir,
                    task_file=task_file,
                    submission_dir=workspace_submission_dir,
                    agent_output_dir=agent_output_dir,
                    task_text=task_file.read_text(encoding="utf-8"),
                )
                try:
                    if agent_docker:
                        agent_result = run_agent_in_docker(
                            retry_context,
                            primary_config,
                            image=agent_docker_image,
                            stdout_log=stdout_log,
                            stderr_log=stderr_log,
                        )
                    else:
                        adapter = get_agent_adapter(primary_config.agent)
                        agent_result = adapter.run(
                            retry_context,
                            primary_config,
                            stdout_log=stdout_log,
                            stderr_log=stderr_log,
                        )
                except ValueError as exc:
                    agent_result = None
                    errors.append(
                        f"contract_closure_gate infrastructure retry failed: {exc}"
                    )
                infrastructure_retry["attempts_used"] = 1
                infrastructure_retry["first_attempt_dir"] = str(first_attempt_dir)
                if agent_result is not None:
                    primary_attempts.append(
                        _closure_agent_compact(agent_result, agent_output_dir) or {}
                    )
                    retry_usage = _collect_agent_usage(agent_result.name, agent_output_dir)
                    infrastructure_retry["retry_exit_status"] = retry_usage.get(
                        "exit_status", ""
                    )
                    infrastructure_retry["retry_passed"] = agent_result.passed

            try:
                closure_initial = check_workspace_isolated(
                    workspace_dir,
                    use_docker=bool(agent_docker),
                    docker_image=agent_docker_image if agent_docker else None,
                    check_mode=closure_check_mode,
                )
            except Exception as exc:  # noqa: BLE001 - preserve evaluator path
                closure_initial = _contract_closure_checker_error(exc)
            closure_final = closure_initial
            repair_rounds_used = 0
            repair_agent_result = None
            repair_decision = decide_repair(
                workspace_dir,
                closure_initial,
                lite=closure_lite and not closure_v1,
                frozen_v1=closure_v1,
                rescue=closure_rescue,
                rescue_plus=closure_rescue_plus,
                v3=closure_v3,
            )
            if (
                repair_decision.get("eligible")
                and repair_decision.get("repair_kind") == "defect_repair"
                and DEFAULT_REPAIR_ROUNDS > 0
            ):
                repair_rounds_used = 1
                repair_kind = "defect_repair"
                repair_task = prepare_repair_workspace(
                    workspace_dir,
                    check_result=closure_initial,
                    task_markdown=task_file.read_text(encoding="utf-8"),
                    lite=closure_lite,
                    rescue_plus=closure_rescue_plus,
                    repair_kind=repair_kind,
                    v3=closure_v3,
                )
                repair_dir = output_path / "agent_repair"
                _reset_dir(repair_dir)
                repair_stdout = repair_dir / "stdout.log"
                repair_stderr = repair_dir / "stderr.log"
                repair_env = {
                    **(run_config.env or {}),
                    CONTRACT_CLOSURE_GATE_ENV: "0" if closure_lite else "1",
                    CONTRACT_CLOSURE_GATE_LITE_ENV: (
                        "1"
                        if closure_lite
                        and not closure_v1
                        and not closure_rescue
                        and not closure_rescue_plus
                        and not closure_v3
                        else "0"
                    ),
                    CONTRACT_CLOSURE_GATE_LITE_V1_ENV: "1" if closure_v1 else "0",
                    CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV: (
                        "1" if closure_rescue else "0"
                    ),
                    CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV: (
                        "1" if closure_rescue_plus else "0"
                    ),
                    CONTRACT_CLOSURE_GATE_V3_ENV: "1" if closure_v3 else "0",
                    CONTRACT_CLOSURE_PHASE_ENV: "repair",
                }
                repair_steps = _positive_env_int(
                    repair_env,
                    REPAIR_MAX_STEPS_ENV,
                    default=(
                        DEFAULT_LITE_V1_REPAIR_MAX_STEPS
                        if closure_v1
                        else DEFAULT_LITE_REPAIR_MAX_STEPS
                        if closure_lite
                        else DEFAULT_REPAIR_MAX_STEPS
                    ),
                )
                repair_env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"] = str(
                    repair_steps or DEFAULT_REPAIR_MAX_STEPS
                )
                repair_limit = _positive_env_int(
                    repair_env,
                    REPAIR_TOKEN_LIMIT_ENV,
                    default=(
                        DEFAULT_LITE_V1_REPAIR_TOKEN_LIMIT
                        if closure_v1
                        else DEFAULT_LITE_REPAIR_TOKEN_LIMIT
                        if closure_lite
                        else None
                    ),
                )
                if repair_limit is not None:
                    repair_env[TOTAL_TOKEN_LIMIT_ENV] = str(repair_limit)
                repair_config = replace(
                    run_config,
                    timeout_seconds=min(
                        int(run_config.timeout_seconds or 3600),
                        DEFAULT_REPAIR_TIMEOUT_SECONDS,
                    ),
                    env=repair_env,
                )
                repair_context = AgentRunContext(
                    workspace_dir=workspace_dir,
                    task_file=workspace_dir / "TASK.md",
                    submission_dir=workspace_submission_dir,
                    agent_output_dir=repair_dir,
                    task_text=repair_task,
                )
                try:
                    if agent_docker:
                        repair_agent_result = run_agent_in_docker(
                            repair_context,
                            repair_config,
                            image=agent_docker_image,
                            stdout_log=repair_stdout,
                            stderr_log=repair_stderr,
                        )
                    else:
                        adapter = get_agent_adapter(repair_config.agent)
                        repair_agent_result = adapter.run(
                            repair_context,
                            repair_config,
                            stdout_log=repair_stdout,
                            stderr_log=repair_stderr,
                        )
                except ValueError as exc:
                    errors.append(f"contract_closure_gate repair failed: {exc}")
                try:
                    closure_final = check_workspace_isolated(
                        workspace_dir,
                        use_docker=bool(agent_docker),
                        docker_image=agent_docker_image if agent_docker else None,
                        check_mode=closure_check_mode,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve evaluator path
                    closure_final = _contract_closure_checker_error(exc)

            contract_closure_audit = write_contract_closure_audit(
                output_path,
                initial=closure_initial,
                final=closure_final,
                repair_rounds_used=repair_rounds_used,
                agent_primary=_closure_agent_compact(agent_result, agent_output_dir),
                agent_repair=_closure_agent_compact(repair_agent_result, output_path / "agent_repair"),
                arm=ablation.ablation_arm,
                repair_decision=repair_decision,
                agent_primary_attempts=primary_attempts,
                infrastructure_retry=infrastructure_retry,
            )
        elif agent_ready and ablation.adaptive_budget_v2:
            from .adaptive_budget_v2 import ADAPTIVE_BUDGET_V2_PHASE_ENV
            from .adaptive_budget_v2 import DEFAULT_EXTRA_TOKEN_LIMIT
            from .adaptive_budget_v2 import DEFAULT_MAX_STEPS
            from .adaptive_budget_v2 import evaluate_progress
            from .adaptive_budget_v2 import extra_token_limit
            from .adaptive_budget_v2 import primary_needs_checkpoint
            from .adaptive_budget_v2 import primary_token_limit
            from .adaptive_budget_v2 import recent_action_window
            from .adaptive_budget_v2 import targeted_repair_task_appendix
            from .adaptive_budget_v2 import write_audit as write_v2_audit
            from .adaptive_budget_v2 import write_checkpoint
            from .llm_usage_proxy import TOTAL_TOKEN_LIMIT_ENV

            def _v2_agent_compact(
                result: Any, output_dir: Path
            ) -> dict[str, Any] | None:
                if result is None:
                    return None
                return {
                    "name": result.name,
                    "passed": result.passed,
                    "returncode": result.returncode,
                    "duration_seconds": result.duration_seconds,
                    "timed_out": result.timed_out,
                    "reason": result.reason,
                    "resource_limited": result.resource_limited,
                    "usage": _collect_agent_usage(result.name, output_dir),
                }

            primary_env = dict(run_config.env or {})
            primary_env[ADAPTIVE_BUDGET_V2_PHASE_ENV] = "primary"
            primary_limit = primary_token_limit(primary_env)
            primary_env.setdefault(TOTAL_TOKEN_LIMIT_ENV, str(primary_limit))
            primary_env.setdefault(
                "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS",
                str(DEFAULT_MAX_STEPS),
            )
            primary_config = replace(run_config, env=primary_env)
            repair_agent_result = None
            repair_rounds_used = 0
            checkpoint_payload: dict[str, Any] = {}

            try:
                if agent_docker:
                    agent_result = run_agent_in_docker(
                        context,
                        primary_config,
                        image=agent_docker_image,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
                else:
                    adapter = get_agent_adapter(primary_config.agent)
                    agent_result = adapter.run(
                        context,
                        primary_config,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
            except ValueError as exc:
                errors.append(f"adaptive_budget_v2 primary run failed: {exc}")

            primary_usage = _collect_agent_usage(
                (agent_result.name if agent_result is not None else config.agent),
                agent_output_dir,
            )
            extra_limit = extra_token_limit(primary_env)
            needs_check = primary_needs_checkpoint(
                primary_usage, primary_limit=primary_limit
            )
            if not needs_check:
                checkpoint_payload = write_checkpoint(
                    agent_output_dir,
                    signals=evaluate_progress(
                        agent_output_dir=agent_output_dir,
                        submission_dir=workspace_submission_dir,
                        recent_n=recent_action_window(primary_env),
                    ),
                    primary_usage=primary_usage,
                    primary_limit=primary_limit,
                    extra_limit=extra_limit,
                    granted_extra=False,
                )
                checkpoint_payload["decision"] = "skip_voluntary_finish"
                checkpoint_payload["reason"] = "primary_finished_below_checkpoint_threshold"
                checkpoint_payload["granted_extra"] = False
                (agent_output_dir / "v2_checkpoint.json").write_text(
                    json.dumps(checkpoint_payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            else:
                signals = evaluate_progress(
                    agent_output_dir=agent_output_dir,
                    submission_dir=workspace_submission_dir,
                    recent_n=recent_action_window(primary_env),
                )
                grant_extra = signals.decision == "continue"
                checkpoint_payload = write_checkpoint(
                    agent_output_dir,
                    signals=signals,
                    primary_usage=primary_usage,
                    primary_limit=primary_limit,
                    extra_limit=extra_limit,
                    granted_extra=grant_extra,
                )
                if grant_extra:
                    task_path_ws = workspace_dir / "TASK.md"
                    try:
                        existing = task_path_ws.read_text(encoding="utf-8")
                    except OSError:
                        existing = context.task_text or ""
                    if "## Targeted Repair Mode" not in existing:
                        task_path_ws.write_text(
                            existing.rstrip() + "\n\n" + targeted_repair_task_appendix(),
                            encoding="utf-8",
                        )
                    repair_dir = output_path / "agent_repair"
                    _reset_dir(repair_dir)
                    repair_stdout = repair_dir / "stdout.log"
                    repair_stderr = repair_dir / "stderr.log"
                    repair_env = {
                        **(run_config.env or {}),
                        ADAPTIVE_BUDGET_V2_PHASE_ENV: "repair",
                        TOTAL_TOKEN_LIMIT_ENV: str(extra_limit or DEFAULT_EXTRA_TOKEN_LIMIT),
                        "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS": str(
                            primary_env.get(
                                "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS",
                                str(DEFAULT_MAX_STEPS),
                            )
                        ),
                    }
                    repair_config = replace(
                        run_config,
                        timeout_seconds=min(
                            int(run_config.timeout_seconds or 3600),
                            1800,
                        ),
                        env=repair_env,
                    )
                    repair_context = AgentRunContext(
                        workspace_dir=workspace_dir,
                        task_file=task_path_ws,
                        submission_dir=workspace_submission_dir,
                        agent_output_dir=repair_dir,
                        task_text=task_path_ws.read_text(encoding="utf-8"),
                    )
                    try:
                        if agent_docker:
                            repair_agent_result = run_agent_in_docker(
                                repair_context,
                                repair_config,
                                image=agent_docker_image,
                                stdout_log=repair_stdout,
                                stderr_log=repair_stderr,
                            )
                        else:
                            adapter = get_agent_adapter(repair_config.agent)
                            repair_agent_result = adapter.run(
                                repair_context,
                                repair_config,
                                stdout_log=repair_stdout,
                                stderr_log=repair_stderr,
                            )
                        repair_rounds_used = 1
                    except ValueError as exc:
                        errors.append(
                            f"adaptive_budget_v2 targeted repair failed: {exc}"
                        )

            adaptive_budget_v2_audit = write_v2_audit(
                output_path,
                checkpoint=checkpoint_payload,
                agent_primary=_v2_agent_compact(agent_result, agent_output_dir),
                agent_repair=_v2_agent_compact(
                    repair_agent_result, output_path / "agent_repair"
                ),
                repair_rounds_used=repair_rounds_used,
            )
        elif agent_ready:
            try:
                if agent_docker:
                    agent_result = run_agent_in_docker(
                        context,
                        run_config,
                        image=agent_docker_image,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
                else:
                    adapter = get_agent_adapter(run_config.agent)
                    agent_result = adapter.run(
                        context,
                        run_config,
                        stdout_log=stdout_log,
                        stderr_log=stderr_log,
                    )
            except ValueError as exc:
                errors.append(str(exc))
        if agent_result is not None and not stdout_log.is_file():
            _write_agent_logs(agent_output_dir, agent_result)

        if _has_submission_files(workspace_submission_dir):
            _copy_submission(workspace_submission_dir, collected_submission_dir)
            eval_result = _evaluate_collected_submission(
                task_path=task_path,
                collected_submission_dir=collected_submission_dir,
                eval_output_dir=eval_output_dir,
                eval_docker=eval_docker,
                eval_docker_image=eval_docker_image,
            )
        else:
            recovery_info = _recover_misplaced_submission(workspace_dir, workspace_submission_dir)
            if recovery_info is not None and recovery_info.get("message"):
                errors.append(str(recovery_info["message"]))
            if _has_submission_files(workspace_submission_dir):
                _copy_submission(workspace_submission_dir, collected_submission_dir)
                eval_result = _evaluate_collected_submission(
                    task_path=task_path,
                    collected_submission_dir=collected_submission_dir,
                    eval_output_dir=eval_output_dir,
                    eval_docker=eval_docker,
                    eval_docker_image=eval_docker_image,
                )
            else:
                if agent_ready:
                    errors.append("agent did not create any files under workspace/submission")
                    errors.append(_missing_submission_diagnostic(workspace_dir))
                # TFL: freeze fail / missing submission still count in suite
                # denominator; formal metrics are recorded as not_evaluated.

        if ablation.test_first_lift:
            from .test_first_lift import write_phase_audit

            try:
                agent_compact = None
                if agent_result is not None:
                    agent_compact = {
                        "name": agent_result.name,
                        "passed": agent_result.passed,
                        "returncode": agent_result.returncode,
                        "duration_seconds": agent_result.duration_seconds,
                        "timed_out": agent_result.timed_out,
                        "reason": agent_result.reason,
                        "resource_limited": agent_result.resource_limited,
                    }
                write_phase_audit(
                    output_path,
                    workspace_dir=workspace_dir,
                    agent_result=agent_compact,
                    evaluation=_evaluation_payload(eval_result, eval_output_dir),
                    submission_exists=_has_submission_files(collected_submission_dir),
                )
            except Exception as exc:  # noqa: BLE001 - audit must not kill eval
                errors.append(f"test_first_lift audit failed: {exc}")

        if repo_graph_state is not None:
            try:
                repo_graph_usage = finalize_repo_graph(
                    repo_graph_state,
                    submission_dir=workspace_submission_dir,
                )
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"repository graph post-run audit failed: {exc}")

    agent_payload: dict[str, Any]
    if agent_result is None:
        agent_payload = {
            "name": config.agent,
            "command": [],
            "returncode": None,
            "passed": False,
            "duration_seconds": 0.0,
            "timed_out": False,
            "reason": "",
            "resource_limited": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
            "log_limit_exceeded": False,
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
        }
    else:
        agent_payload = agent_result.payload(stdout_log=stdout_log, stderr_log=stderr_log)
    agent_payload["usage"] = _collect_agent_usage(config.agent, agent_output_dir)

    submission_exists = _has_submission_files(collected_submission_dir)
    evaluation_payload = _evaluation_payload(eval_result, eval_output_dir)
    status = _run_status(
        validation_ok=validation.valid,
        agent_passed=agent_payload["passed"],
        submission_exists=submission_exists,
        eval_result=eval_result,
    )
    # In this experimental arm the private evaluator remains the formal outcome;
    # primary/repair termination and closure state are recorded independently.
    if (
        (
            ablation.contract_closure_gate
            or ablation.contract_closure_gate_lite
            or ablation.contract_closure_gate_lite_v1
            or ablation.contract_closure_gate_lite_rescue
            or ablation.contract_closure_gate_lite_rescue_plus
            or ablation.contract_closure_gate_v3
            or ablation.contract_closure_budget_control
        )
        and validation.valid
        and submission_exists
        and eval_result is not None
        and eval_result.get("status") == "passed"
    ):
        status = "passed"
    if pre_agent_failure:
        status = "failed"
    run_json_path = output_path / "run.json"
    submission_payload: dict[str, Any] = {
        "dir": str(collected_submission_dir),
        "exists": submission_exists,
        "recovered": bool(recovery_info and recovery_info.get("recovered")),
    }
    recovery_sources = recovery_info.get("recovery_sources") if isinstance(recovery_info, dict) else None
    if isinstance(recovery_sources, list) and recovery_sources:
        submission_payload["recovery_sources"] = recovery_sources
    result = {
        "mode": "task",
        "generated_at": _utc_now(),
        "task_id": task_id,
        "status": status,
        "attempt": next_attempt,
        "agent": agent_payload,
        "agent_backend": "docker" if agent_docker else "local",
        "agent_docker_image": agent_docker_image if agent_docker else "",
        "agent_config": agent_config_summary or {},
        "ablation": ablation.summary(),
        "benchmark_freeze": freeze_provenance or {},
        "experiment_conditions": _experiment_conditions(
            config=config,
            ablation=ablation.summary(),
            benchmark_freeze=freeze_provenance,
            source=source_provenance,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
            eval_docker=eval_docker,
            eval_docker_image=eval_docker_image,
            extra=source_ablation_condition_fields(ablation, config.env),
        ),
        "source": source_provenance or {},
        "workspace": _workspace_payload(
            workspace_dir,
            agent_output_dir=agent_output_dir,
            ablation=ablation,
            env=config.env,
        ),
        "submission": submission_payload,
        "evaluation": evaluation_payload,
        "eval_backend": "docker" if eval_docker else "local",
        "eval_docker_image": eval_docker_image if eval_docker else "",
        "errors": errors,
        "run_json": str(run_json_path),
    }
    if repo_graph_usage is not None:
        result["repo_graph"] = repo_graph_usage
    if contract_closure_audit is not None:
        result["contract_closure"] = contract_closure_audit
    if adaptive_budget_v2_audit is not None:
        result["adaptive_budget_v2"] = adaptive_budget_v2_audit
    if previous_attempt_json is not None:
        result["previous_attempt_json"] = previous_attempt_json
    run_json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


@lru_cache(maxsize=16)
def _docker_image_identity(image: str) -> str:
    completed = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def _experiment_conditions(
    *,
    config: AgentRunConfig,
    ablation: dict[str, Any],
    benchmark_freeze: dict[str, Any] | None,
    source: dict[str, Any] | None,
    agent_docker: bool,
    agent_docker_image: str,
    eval_docker: bool,
    eval_docker_image: str,
    evaluation: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = config.env or {}
    payload = {
        "schema_version": "featureliftbench.experiment_conditions.v2",
        "benchmark_policy_id": (
            benchmark_freeze.get("policy_id") if benchmark_freeze else None
        ),
        "benchmark_freeze_id": (
            benchmark_freeze.get("freeze_id") if benchmark_freeze else None
        ),
        "source_snapshot_id": (
            source.get("source_snapshot_id") if source else None
        ),
        "source_tree_sha256": source.get("source_digest") if source else None,
        "source_scope": source.get("snapshot_scope") if source else None,
        "model": config.model or "",
        "agent": config.agent,
        "agent_profile": config.profile,
        "agent_timeout_seconds": config.timeout_seconds,
        "agent_max_steps": env.get("FEATURELIFTBENCH_OPENHANDS_MAX_STEPS", ""),
        "ablation": ablation,
        "agent_runtime": {
            "backend": "docker" if agent_docker else "local",
            "image": agent_docker_image if agent_docker else "",
            "image_id": (
                _docker_image_identity(agent_docker_image)
                if agent_docker
                else ""
            ),
        },
        "evaluator_runtime": {
            "backend": "docker" if eval_docker else "local",
            "image": eval_docker_image if eval_docker else "",
            "image_id": (
                _docker_image_identity(eval_docker_image)
                if eval_docker
                else ""
            ),
            "network": "none" if eval_docker else "host",
        },
        "benchmark_tests_visible_to_agent": bool(
            ablation.get("mount_public_tests")
        ),
        "source_hints_visible_to_agent": bool(
            ablation.get("expose_source_hints")
        ),
        "evaluation_capsule_digest": (
            evaluation.get("evaluation_capsule_digest")
            if isinstance(evaluation, dict)
            else None
        ),
    }
    if extra:
        payload.update(extra)
    return payload


def _workspace_payload(
    workspace_dir: Path,
    *,
    agent_output_dir: Path,
    ablation: AblationOptions,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "dir": str(workspace_dir),
        "task_file": str(workspace_dir / "TASK.md"),
        "public_tests_mounted": ablation.mount_public_tests,
    }
    extra = source_ablation_condition_fields(ablation, env)
    if extra:
        payload.update(extra)
        inventory = agent_output_dir / VISIBLE_INVENTORY_NAME
        if inventory.is_file():
            payload["visible_inventory"] = str(inventory)
    return payload


def _validate_retained_runs(
    retained_runs: dict[str, dict[str, Any]],
    *,
    task_dirs: list[Path],
    config: AgentRunConfig,
    agent_docker: bool,
    agent_docker_image: str,
    eval_docker: bool,
    eval_docker_image: str,
) -> None:
    if not retained_runs:
        return
    task_paths = {path.name: path for path in task_dirs}
    expected_ablation = ablation_options_from_env(config.env).summary()
    expected_common = {
        "model": config.model or "",
        "agent": config.agent,
        "agent_profile": config.profile,
        "agent_timeout_seconds": config.timeout_seconds,
        "agent_max_steps": (config.env or {}).get(
            "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS",
            "",
        ),
        "ablation": expected_ablation,
        "agent_runtime": {
            "backend": "docker" if agent_docker else "local",
            "image": agent_docker_image if agent_docker else "",
            "image_id": (
                _docker_image_identity(agent_docker_image)
                if agent_docker
                else ""
            ),
        },
        "evaluator_runtime": {
            "backend": "docker" if eval_docker else "local",
            "image": eval_docker_image if eval_docker else "",
            "image_id": (
                _docker_image_identity(eval_docker_image)
                if eval_docker
                else ""
            ),
            "network": "none" if eval_docker else "host",
        },
        "benchmark_tests_visible_to_agent": bool(
            expected_ablation.get("mount_public_tests")
        ),
        "source_hints_visible_to_agent": bool(
            expected_ablation.get("expose_source_hints")
        ),
    }
    failures: list[str] = []
    for task_id, run in sorted(retained_runs.items()):
        task_path = task_paths.get(task_id)
        require_freeze = bool(task_path and _is_python_main_task(task_path))
        active = benchmark_freeze_provenance(task_id, require=require_freeze)
        recorded = run.get("benchmark_freeze")
        if active is not None:
            if not isinstance(recorded, dict):
                failures.append(f"{task_id}: retained run lacks benchmark freeze")
                continue
            for key in (
                "freeze_id",
                "task_revision",
                "spec_hash",
                "source_snapshot_id",
                "source_tree_sha256",
            ):
                if recorded.get(key) != active.get(key):
                    failures.append(f"{task_id}: retained {key} differs")
        conditions = run.get("experiment_conditions")
        if require_freeze and not isinstance(conditions, dict):
            failures.append(f"{task_id}: retained run lacks experiment conditions")
            continue
        if not isinstance(conditions, dict):
            continue
        for key, expected in expected_common.items():
            if conditions.get(key) != expected:
                failures.append(f"{task_id}: retained experiment {key} differs")
    if failures:
        raise ValueError(
            "resume would mix incompatible benchmark/experiment conditions:\n"
            + "\n".join(failures[:20])
        )


def _write_repo_graph_initialization_failure(
    agent_output_dir: Path,
    *,
    policy: RepoGraphPolicy,
    error: Exception,
) -> None:
    (agent_output_dir / "repo_graph_policy.json").write_text(
        json.dumps(policy.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (agent_output_dir / "repo_graph_build.json").write_text(
        json.dumps(
            {
                "schema_version": "featureliftbench.repo_graph.run.v1",
                "status": "initialization_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "model_invoked": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _evaluate_collected_submission(
    *,
    task_path: Path,
    collected_submission_dir: Path,
    eval_output_dir: Path,
    eval_docker: bool,
    eval_docker_image: str,
) -> dict[str, Any]:
    if eval_docker:
        return evaluate_submission_docker(
            task_path,
            collected_submission_dir,
            eval_output_dir,
            image=eval_docker_image,
            use_docker=True,
        )
    return evaluate_submission(task_path, collected_submission_dir, eval_output_dir)


def _run_suite_tasks(
    *,
    task_dirs: list[Path],
    output_path: Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None,
    num_workers: int,
    progress: bool,
    retry_rate_limit: int = 1,
    retry_transient_api: int = 3,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
    checkpoint_ctx: _SuiteCheckpointContext | None = None,
) -> list[dict[str, Any]]:
    total = len(task_dirs)
    use_live_progress = progress and sys.stderr.isatty() and total > 1

    if use_live_progress:
        with live_suite_progress(num_tasks=total, output_dir=output_path) as progress_manager:
            return _execute_suite_tasks(
                task_dirs=task_dirs,
                output_path=output_path,
                config=config,
                agent_config_summary=agent_config_summary,
                num_workers=num_workers,
                total=total,
                progress_manager=progress_manager,
                retry_rate_limit=retry_rate_limit,
                retry_transient_api=retry_transient_api,
                eval_docker=eval_docker,
                eval_docker_image=eval_docker_image,
                agent_docker=agent_docker,
                agent_docker_image=agent_docker_image,
                checkpoint_ctx=checkpoint_ctx,
            )

    return _execute_suite_tasks(
        task_dirs=task_dirs,
        output_path=output_path,
        config=config,
        agent_config_summary=agent_config_summary,
        num_workers=num_workers,
        total=total,
        progress=progress,
        progress_manager=None,
        retry_rate_limit=retry_rate_limit,
        retry_transient_api=retry_transient_api,
        eval_docker=eval_docker,
        eval_docker_image=eval_docker_image,
        agent_docker=agent_docker,
        agent_docker_image=agent_docker_image,
        checkpoint_ctx=checkpoint_ctx,
    )


def _execute_suite_tasks(
    *,
    task_dirs: list[Path],
    output_path: Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None,
    num_workers: int,
    total: int,
    progress: bool = False,
    progress_manager: SuiteBatchProgressManager | None = None,
    retry_rate_limit: int = 1,
    retry_transient_api: int = 3,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
    checkpoint_ctx: _SuiteCheckpointContext | None = None,
) -> list[dict[str, Any]]:
    if num_workers == 1:
        runs = []
        try:
            for index, task_dir in enumerate(task_dirs, start=1):
                runs.append(
                    _run_suite_task_safely(
                        index=index,
                        total=total,
                        task_dir=task_dir,
                        output_path=output_path,
                        config=config,
                        agent_config_summary=agent_config_summary,
                        progress=progress and progress_manager is None,
                        progress_manager=progress_manager,
                        retry_rate_limit=retry_rate_limit,
                        retry_transient_api=retry_transient_api,
                        eval_docker=eval_docker,
                        eval_docker_image=eval_docker_image,
                        agent_docker=agent_docker,
                        agent_docker_image=agent_docker_image,
                    )
                )
                if checkpoint_ctx is not None:
                    _write_suite_checkpoint(checkpoint_ctx, runs)
        except KeyboardInterrupt:
            _stop_suite_run()
            raise SystemExit(130) from None
        return runs

    runs_by_index: dict[int, dict[str, Any]] = {}
    executor = ThreadPoolExecutor(max_workers=num_workers)
    futures = {
        executor.submit(
            _run_suite_task_safely,
            index=index,
            total=total,
            task_dir=task_dir,
            output_path=output_path,
            config=config,
            agent_config_summary=agent_config_summary,
            progress=progress and progress_manager is None,
            progress_manager=progress_manager,
            retry_rate_limit=retry_rate_limit,
            retry_transient_api=retry_transient_api,
            eval_docker=eval_docker,
            eval_docker_image=eval_docker_image,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        ): index
        for index, task_dir in enumerate(task_dirs, start=1)
    }
    try:
        for future in as_completed(futures):
            index = futures[future]
            try:
                runs_by_index[index] = future.result()
            except Exception as exc:  # Defensive: keep suite output complete.
                task_dir = task_dirs[index - 1]
                runs_by_index[index] = _exception_run_result(
                    task_dir,
                    output_path / task_dir.name,
                    config,
                    agent_config_summary,
                    exc,
                    progress_manager=progress_manager,
                    agent_docker=agent_docker,
                    agent_docker_image=agent_docker_image,
                )
            if checkpoint_ctx is not None:
                completed = [runs_by_index[i] for i in sorted(runs_by_index)]
                _write_suite_checkpoint(checkpoint_ctx, completed)
    except KeyboardInterrupt:
        _stop_suite_run()
        for future in futures:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise SystemExit(130) from None
    else:
        executor.shutdown(wait=True)
    return [runs_by_index[index] for index in range(1, total + 1)]


def _stop_suite_run() -> None:
    print("\nStopping suite run and terminating active agent processes...", file=sys.stderr, flush=True)
    terminate_active_agent_processes()


def _run_suite_task_safely(
    *,
    index: int,
    total: int,
    task_dir: Path,
    output_path: Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None,
    progress: bool,
    progress_manager: SuiteBatchProgressManager | None = None,
    retry_rate_limit: int = 1,
    retry_transient_api: int = 3,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> dict[str, Any]:
    task_id = task_dir.name
    if progress_manager is not None:
        progress_manager.on_task_start(task_id)
        progress_manager.update_task_status(task_id, "preparing workspace")
    else:
        _progress(progress, f"[{index}/{total}] started {task_id}")

    run_output = output_path / task_id
    try:
        result = _run_suite_task_with_retries(
            task_dir=task_dir,
            run_output=run_output,
            config=config,
            agent_config_summary=agent_config_summary,
            retry_rate_limit=retry_rate_limit,
            retry_transient_api=retry_transient_api,
            eval_docker=eval_docker,
            eval_docker_image=eval_docker_image,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )
    except Exception as exc:  # Defensive: one task should not abort the suite.
        result = _exception_run_result(
            task_dir,
            run_output,
            config,
            agent_config_summary,
            exc,
            progress_manager=progress_manager,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )

    status = result.get("status", "failed")
    if progress_manager is not None:
        progress_manager.on_task_end(task_id, status)
    else:
        _progress(progress, f"[{index}/{total}] finished {task_id}: {status}")
    return result


def _exception_run_result(
    task_dir: Path,
    output_dir: Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None,
    exc: Exception,
    progress_manager: SuiteBatchProgressManager | None = None,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_json_path = output_dir / "run.json"
    result = {
        "mode": "task",
        "generated_at": _utc_now(),
        "task_id": task_dir.name,
        "status": "failed",
        "agent": {
            "name": config.agent,
            "command": [],
            "returncode": None,
            "passed": False,
            "duration_seconds": 0.0,
            "timed_out": False,
            "reason": "suite task raised an exception",
            "resource_limited": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
            "log_limit_exceeded": False,
            "usage": _unavailable_agent_usage(output_dir / "agent" / "usage.json", "task raised before usage was available"),
        },
        "agent_backend": "docker" if agent_docker else "local",
        "agent_docker_image": agent_docker_image if agent_docker else "",
        "agent_config": agent_config_summary or {},
        "workspace": {
            "dir": str(output_dir / "workspace"),
            "task_file": str(output_dir / "workspace" / "TASK.md"),
        },
        "submission": {
            "dir": str(output_dir / "submission"),
            "exists": False,
        },
        "evaluation": {
            "dir": str(output_dir / "eval"),
            "result_json": "",
            "status": "not-run",
            "scores": {},
        },
        "errors": [
            f"{type(exc).__name__}: {exc}",
            traceback.format_exc(),
        ],
        "run_json": str(run_json_path),
    }
    run_json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _progress(enabled: bool, message: str) -> None:
    if enabled:
        try:
            print(message, file=sys.stderr, flush=True)
        except BrokenPipeError:
            # The run may outlive an attached terminal or API tool stream.
            # Progress output is best-effort and must never invalidate a task.
            pass


def discover_task_dirs(input_path: str | Path, task_ids: list[str] | None = None) -> list[Path]:
    """Discover task directories from either a task dir or a dataset root."""

    path = resolve_task_input(input_path)
    hard_only = path.resolve() == resolve_task_input("benchmark/tasks").resolve()
    return discover_main_task_dirs(path, task_ids=task_ids, hard_only=hard_only)


def load_skipped_runs(skip_dir: str | Path | None) -> dict[str, dict[str, Any]]:
    """Load passed task run.json payloads from a previous suite output directory."""

    return load_retained_runs(skip_dir, retain_statuses=frozenset({"passed"}))


def _resolve_suite_source_dir(
    *,
    output_path: Path,
    resume_dir: str | Path | None,
    resume_mode: bool,
    skip_completed_dir: str | Path | None,
) -> Path | None:
    if resume_dir is not None:
        return Path(resume_dir).resolve()
    if resume_mode:
        return output_path
    if skip_completed_dir is not None:
        return Path(skip_completed_dir).resolve()
    return None


def _resolve_retain_statuses(
    *,
    resume_mode: bool,
    skip_completed_dir: str | Path | None,
    retry_only_statuses: frozenset[str],
) -> frozenset[str]:
    if resume_mode:
        return ALL_RUN_STATUSES - retry_only_statuses
    if skip_completed_dir is not None:
        return frozenset({"passed"})
    return frozenset()


def _load_existing_runs(output_path: Path, task_ids: set[str]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for task_id in sorted(task_ids):
        run_json = output_path / task_id / "run.json"
        if not run_json.is_file():
            continue
        try:
            payload = json.loads(run_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            runs[task_id] = payload
    return runs


def _merge_retained_runs(
    primary: dict[str, dict[str, Any]],
    secondary: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = dict(primary)
    for task_id, run in secondary.items():
        merged.setdefault(task_id, run)
    return merged


def _read_task_attempt(task_run_dir: Path) -> int:
    run_json_path = task_run_dir / "run.json"
    if not run_json_path.is_file():
        return 0
    try:
        data = json.loads(run_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    attempt = data.get("attempt", 1)
    if isinstance(attempt, int) and attempt >= 1:
        return attempt
    return 1


def _task_at_max_attempts(task_run_dir: Path, max_task_attempts: int | None) -> bool:
    if max_task_attempts is None or max_task_attempts < 1:
        return False
    return _read_task_attempt(task_run_dir) >= max_task_attempts


def _tasks_at_max_attempts(
    task_dirs: list[Path],
    output_path: Path,
    max_task_attempts: int | None,
    *,
    exclude_task_ids: set[str],
) -> set[str]:
    if max_task_attempts is None or max_task_attempts < 1:
        return set()
    skipped: set[str] = set()
    for task_dir in task_dirs:
        task_id = task_dir.name
        if task_id in exclude_task_ids:
            continue
        if _task_at_max_attempts(output_path / task_id, max_task_attempts):
            skipped.add(task_id)
    return skipped


def _archive_previous_run(output_path: Path) -> tuple[int, str | None]:
    run_json_path = output_path / "run.json"
    if not run_json_path.is_file():
        return 1, None
    try:
        data = json.loads(run_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 1, None
    current_attempt = data.get("attempt", 1)
    if not isinstance(current_attempt, int) or current_attempt < 1:
        current_attempt = 1
    archive_name = f"run.attempt{current_attempt}.json"
    archive_path = output_path / archive_name
    shutil.copy2(run_json_path, archive_path)
    return current_attempt + 1, str(archive_path)


def _write_suite_snapshot(
    snapshot_path: Path,
    *,
    runs: list[dict[str, Any]],
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None,
    output_path: Path,
    worker_count: int,
    retry_rate_limit: int,
    retry_transient_api: int,
    retry_only_statuses: frozenset[str],
    extra_agent_passes: int,
    pass_index: int,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> None:
    snapshot = {
        "mode": "suite_snapshot",
        "generated_at": _utc_now(),
        "pass_index": pass_index,
        "agent": config.agent,
        "agent_backend": "docker" if agent_docker else "local",
        "agent_docker_image": agent_docker_image if agent_docker else "",
        "output_dir": str(output_path),
        "retry_only_statuses": sorted(retry_only_statuses),
        "extra_agent_passes": extra_agent_passes,
        "summary": rebuild_suite_summary(runs),
        "runs": [compact_suite_run_entry(run) for run in runs],
        "num_workers": worker_count,
        "retry_rate_limit": retry_rate_limit,
        "retry_transient_api": retry_transient_api,
        "agent_config": agent_config_summary or {},
    }
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")


def _write_suite_checkpoint(
    ctx: _SuiteCheckpointContext,
    completed_fresh_runs: list[dict[str, Any]],
) -> None:
    merged = _merge_suite_runs(ctx.ordered_task_dirs, completed_fresh_runs, ctx.retained_runs)
    agent_usage_totals = _sum_agent_usage(merged)
    payload = {
        "mode": "suite",
        "checkpoint": True,
        "generated_at": _utc_now(),
        "agent": ctx.config.agent,
        "agent_config": ctx.agent_config_summary or {},
        "output_dir": str(ctx.output_path),
        "num_workers": ctx.worker_count,
        "agent_backend": "docker" if ctx.agent_docker else "local",
        "agent_docker_image": ctx.agent_docker_image if ctx.agent_docker else "",
        "eval_backend": "docker" if ctx.eval_docker else "local",
        "eval_docker_image": ctx.eval_docker_image if ctx.eval_docker else "",
        "retry_rate_limit": ctx.retry_rate_limit,
        "retry_transient_api": ctx.retry_transient_api,
        "retry_only_statuses": sorted(ctx.retry_only_statuses),
        "extra_agent_passes": ctx.extra_agent_passes,
        "max_task_attempts": ctx.max_task_attempts,
        "skipped_completed": sorted(ctx.retained_runs),
        "resume": {
            "enabled": ctx.resume_enabled,
            "source_dir": str(ctx.suite_source_dir) if ctx.suite_source_dir is not None else "",
            "retained": len(ctx.retained_runs),
            "retried": ctx.runnable_count,
            "skipped_max_attempts": sorted(ctx.skipped_max_attempts),
        },
        "summary": rebuild_suite_summary(merged),
        "agent_usage_totals": agent_usage_totals,
        "runs": [compact_suite_run_entry(run) for run in merged],
        "checkpoint_progress": {
            "completed_this_run": len(completed_fresh_runs),
            "runnable_total": ctx.runnable_count,
        },
    }
    (ctx.output_path / "suite.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _merge_suite_runs(
    ordered_task_dirs: list[Path],
    fresh_runs: list[dict[str, Any]],
    skipped_runs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    fresh_by_id = {
        run.get("task_id"): run for run in fresh_runs if isinstance(run.get("task_id"), str)
    }
    merged: list[dict[str, Any]] = []
    for task_dir in ordered_task_dirs:
        task_id = task_dir.name
        if task_id in skipped_runs:
            merged.append(skipped_runs[task_id])
        elif task_id in fresh_by_id:
            merged.append(fresh_by_id[task_id])
    return merged


def _run_suite_task_with_retries(
    *,
    task_dir: Path,
    run_output: Path,
    config: AgentRunConfig,
    agent_config_summary: dict[str, Any] | None,
    retry_rate_limit: int = 1,
    retry_transient_api: int = 3,
    eval_docker: bool = False,
    eval_docker_image: str = DEFAULT_EVAL_IMAGE,
    agent_docker: bool = False,
    agent_docker_image: str = DEFAULT_AGENT_IMAGE,
) -> dict[str, Any]:
    rate_limit_attempts = max(1, int(retry_rate_limit))
    transient_attempts = max(1, int(retry_transient_api))
    result: dict[str, Any] = {}
    reasons: list[str] = []
    attempt = 0
    while True:
        result = run_agent_on_task(
            task_dir,
            run_output,
            config,
            agent_config_summary=agent_config_summary,
            eval_docker=eval_docker,
            eval_docker_image=eval_docker_image,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )
        attempt += 1
        reason = _transient_retry_reason(result)
        if reason is None:
            break
        cap = max(rate_limit_attempts, transient_attempts)
        if attempt >= cap:
            break
        reasons.append(reason)
        wait_seconds = TRANSIENT_API_RETRY_WAIT_SECONDS.get(reason, 8.0)
        task_id = result.get("task_id", task_dir.name)
        print(
            f"Transient API/protocol failure ({reason}) on {task_id}; "
            f"retrying in {wait_seconds:.0f}s "
            f"(attempt {attempt + 1}/{cap})...",
            file=sys.stderr,
            flush=True,
        )
        _preserve_transient_attempt_agent(run_output, attempt)
        time.sleep(wait_seconds)
    if reasons:
        result = _record_transient_retries(
            result,
            run_output,
            attempts=attempt,
            reasons=reasons,
        )
    return result


def _preserve_transient_attempt_agent(run_output: Path, attempt: int) -> None:
    agent_dir = run_output / "agent"
    archive_dir = run_output / f"agent.attempt{attempt}"
    if not agent_dir.is_dir() or archive_dir.exists():
        return
    shutil.copytree(agent_dir, archive_dir, dirs_exist_ok=False)


def _record_transient_retries(
    result: dict[str, Any],
    run_output: Path,
    *,
    attempts: int,
    reasons: list[str],
) -> dict[str, Any]:
    payload = dict(result)
    payload["transient_retries"] = {
        "attempts": attempts,
        "reasons": list(reasons),
        "recovered": payload.get("status") != "missing_submission"
        and bool((payload.get("submission") or {}).get("exists")),
    }
    run_json = payload.get("run_json")
    path = Path(run_json) if isinstance(run_json, str) and run_json else run_output / "run.json"
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
    return payload


def _submission_exists(result: dict[str, Any]) -> bool:
    submission = result.get("submission")
    return isinstance(submission, dict) and submission.get("exists") is True


def _infrastructure_error_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    agent = result.get("agent") if isinstance(result.get("agent"), dict) else {}
    usage = agent.get("usage") if isinstance(agent.get("usage"), dict) else {}
    infra = usage.get("infrastructure_error")
    if isinstance(infra, dict) and infra:
        return infra
    run_json = result.get("run_json")
    if not isinstance(run_json, str) or not run_json:
        return None
    infra_path = Path(run_json).parent / "agent" / "openhands_infrastructure_error.json"
    if not infra_path.is_file():
        return None
    try:
        payload = json.loads(infra_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _collect_retry_evidence_text(result: dict[str, Any]) -> str:
    chunks: list[str] = []
    agent = result.get("agent") if isinstance(result.get("agent"), dict) else {}
    usage = agent.get("usage") if isinstance(agent.get("usage"), dict) else {}
    for value in (
        usage.get("exit_status"),
        agent.get("reason"),
    ):
        if isinstance(value, str) and value:
            chunks.append(value)
    infra = _infrastructure_error_from_result(result)
    if infra is not None:
        for key in ("failure_class", "error"):
            value = infra.get(key)
            if isinstance(value, str) and value:
                chunks.append(value)
    errors = result.get("errors")
    if isinstance(errors, list):
        chunks.extend(str(item) for item in errors)
    run_json = result.get("run_json")
    if isinstance(run_json, str) and run_json:
        events_path = Path(run_json).parent / "agent" / "openhands_events.jsonl"
        if events_path.is_file():
            try:
                chunks.append(events_path.read_text(encoding="utf-8", errors="replace")[-20000:])
            except OSError:
                pass
    return "\n".join(chunks)


def _transient_retry_reason(result: dict[str, Any]) -> str | None:
    """Return a retry class only for empty-submission API/protocol flakes.

    Functional failures that already produced a package are never retried here.
    """

    if result.get("status") == "passed" or _submission_exists(result):
        return None
    if result.get("status") == "invalid_task":
        return None
    infra = _infrastructure_error_from_result(result)
    if isinstance(infra, dict) and infra.get("retryable") is True:
        failure_class = str(infra.get("failure_class") or "")
        if failure_class in TRANSIENT_API_RETRY_WAIT_SECONDS:
            return failure_class
        if failure_class:
            return failure_class
    text = _collect_retry_evidence_text(result)
    if any(pattern.search(text) for pattern in ENCRYPTED_CONTENT_PATTERNS):
        return "invalid_encrypted_content"
    if _is_rate_limit_failure(result):
        return "rate_limit"
    return None


def _is_rate_limit_failure(result: dict[str, Any]) -> bool:
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


def _contract_closure_infrastructure_retry_decision(
    *,
    agent_result: Any,
    agent_output_dir: Path,
    submission_dir: Path,
    enabled: bool,
    retry_limit: int,
    max_trigger_steps: int,
    policy_version: str,
) -> dict[str, Any]:
    """Allow one fresh primary attempt for an explicit early runtime failure."""

    decision: dict[str, Any] = {
        "policy_version": policy_version,
        "requested": False,
        "eligible": False,
        "retry_limit": max(0, int(retry_limit)),
        "max_trigger_steps": max(0, int(max_trigger_steps)),
        "attempts_used": 0,
        "reason": "infrastructure retry not requested",
    }
    if not enabled or agent_result is None:
        decision["reason"] = "infrastructure retry is only enabled for bounded Lite arms"
        return decision

    usage = _collect_agent_usage(agent_result.name, agent_output_dir)
    exit_status = str(usage.get("exit_status") or "")
    assistant_steps = int(usage.get("assistant_steps") or 0)
    submission_empty = not _package_has_python_files(submission_dir)
    requested = exit_status == "tool_validation_error"
    decision.update(
        {
            "requested": requested,
            "exit_status": exit_status,
            "assistant_steps": assistant_steps,
            "submission_empty": submission_empty,
        }
    )
    if not requested:
        decision["reason"] = "primary did not end with a retryable tool validation error"
        return decision
    if retry_limit < 1:
        decision["reason"] = "infrastructure retry limit is zero"
        return decision
    if not submission_empty:
        decision["reason"] = "submission is non-empty; preserve output and use normal closure logic"
        return decision
    if assistant_steps > max_trigger_steps:
        decision["reason"] = (
            f"tool validation error occurred after {assistant_steps} steps, exceeding "
            f"the early-retry threshold of {max_trigger_steps}"
        )
        return decision
    decision["eligible"] = True
    decision["reason"] = (
        "explicit OpenHands tool validation error occurred early with an empty submission"
    )
    return decision


def _contract_closure_checker_error(exc: BaseException) -> dict[str, Any]:
    """Record checker infrastructure errors without spending a model repair."""

    from .contract_closure_gate.common import CHECKER_VERSION

    message = f"{type(exc).__name__}: {exc}"
    return {
        "schema_version": "featureliftbench.contract_closure_check.v1",
        "checker_version": CHECKER_VERSION,
        "check_mode": "full",
        "hard_gate_ok": False,
        "behavior_gate_ok": False,
        "closure_ok": False,
        "repair_needed": False,
        "summary": {"pass": 0, "fail": 0, "unknown": 1},
        "hard_failure_count": 0,
        "actionable_behavior_failure_count": 0,
        "soft_open_count": 0,
        "unknown_count": 1,
        "checker_environment_unknown_count": 1,
        "checks": [
            {
                "id": "checker.infrastructure",
                "category": "infrastructure",
                "status": "unknown",
                "severity": "hard",
                "message": message,
            }
        ],
    }


def _positive_env_int(
    env: dict[str, str],
    key: str,
    *,
    default: int | None = None,
) -> int | None:
    raw = str(env.get(key, "")).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def prepare_agent_workspace(
    task_dir: str | Path,
    workspace_dir: str | Path,
    metadata: dict[str, Any],
    *,
    ablation: AblationOptions | None = None,
) -> Path:
    """Build the redacted workspace visible to the agent and return TASK.md."""

    options = ablation or AblationOptions()
    task_path = Path(task_dir).resolve()
    workspace_path = Path(workspace_dir).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)

    if is_contract_only(options):
        # Supplementary no-source arm: do not materialize or copy the repository.
        source_provenance = None
    elif options.source_context == "pruned_context":
        source_provenance = materialize_pruned_task_source(
            task_path.name,
            workspace_path / "repo",
        )
        if source_provenance is None:
            _copy_path(task_path / "repo", workspace_path / "repo")
    else:
        source_provenance = materialize_task_source(
            task_path.name,
            workspace_path / "repo",
            require_registered=_is_python_main_task(task_path),
        )
        if source_provenance is None:
            _copy_path(task_path / "repo", workspace_path / "repo")
    language = str(metadata.get("language", "python"))
    if options.mount_public_tests:
        _copy_path(
            task_path / _test_path(metadata, "public", "public_tests/"),
            workspace_path / "public_tests",
        )
        if language == "go":
            public_runner = workspace_path / "run_public_tests.sh"
            public_runner.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                "test -f submission/go.mod || { echo 'missing submission/go.mod' >&2; exit 2; }\n"
                "tmp_dir=$(mktemp -d)\n"
                "trap 'rm -rf \"$tmp_dir\"' EXIT INT TERM\n"
                "cp -R submission/. \"$tmp_dir/\"\n"
                "cp public_tests/*_test.go \"$tmp_dir/\"\n"
                "cd \"$tmp_dir\"\n"
                "CGO_ENABLED=0 GOPROXY=off GOSUMDB=off go test ./...\n",
                encoding="utf-8",
            )
            public_runner.chmod(0o755)
    if language == "go":
        go_mod = task_path / "environment" / "go.mod"
        if go_mod.is_file():
            shutil.copy2(go_mod, workspace_path / "go.mod")
        go_sum = task_path / "environment" / "go.sum"
        if go_sum.is_file():
            shutil.copy2(go_sum, workspace_path / "go.sum")
    else:
        lock_path = task_path / _dependency_lock(metadata)
        if lock_path.exists():
            shutil.copy2(lock_path, workspace_path / "requirements.lock")
        else:
            (workspace_path / "requirements.lock").write_text("", encoding="utf-8")

    redacted_metadata = redact_task_metadata(
        metadata,
        expose_source_hints=options.expose_source_hints,
    )
    (workspace_path / "metadata.json").write_text(
        json.dumps(redacted_metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if options.td_cognition:
        from .td_cognition import install_td_cognition_workspace
        from .td_cognition import phase1_task_appendix

        install_td_cognition_workspace(workspace_path)
    elif options.exec_contract:
        from .exec_contract import install_exec_contract_workspace

        install_exec_contract_workspace(workspace_path)
    elif options.self_contract:
        from .self_contract import install_self_contract_workspace

        install_self_contract_workspace(workspace_path)
    elif options.test_first_lift:
        from .test_first_lift import install_test_first_lift_workspace
        from .test_first_lift.cases import flatten_required_api_paths

        install_test_first_lift_workspace(
            workspace_path,
            required_api_paths=flatten_required_api_paths(metadata),
        )
    elif options.spec_adversarial_self_test:
        from .spec_adversarial import install_spec_adversarial_workspace

        public_spec = (
            metadata.get("public_spec")
            if isinstance(metadata.get("public_spec"), dict)
            else {}
        )
        if not isinstance(public_spec, dict) or not public_spec:
            raise ValueError(
                "spec_adversarial_self_test requires metadata.public_spec"
            )
        install_spec_adversarial_workspace(
            workspace_path,
            public_spec=public_spec,
        )
        (workspace_path / "submission").mkdir(exist_ok=True)
    elif options.obligation_guided:
        from .obligation_guided import install_obligation_guided_workspace

        public_spec = (
            metadata.get("public_spec")
            if isinstance(metadata.get("public_spec"), dict)
            else {}
        )
        if not isinstance(public_spec, dict) or not public_spec:
            raise ValueError("obligation_guided requires metadata.public_spec")
        install_obligation_guided_workspace(
            workspace_path,
            public_spec=public_spec,
        )
        (workspace_path / "submission").mkdir(exist_ok=True)
    elif options.cgvl:
        from .cgvl import install_cgvl_workspace

        public_spec = (
            metadata.get("public_spec")
            if isinstance(metadata.get("public_spec"), dict)
            else {}
        )
        if not isinstance(public_spec, dict) or not public_spec:
            raise ValueError("cgvl requires metadata.public_spec")
        install_cgvl_workspace(workspace_path, public_spec=public_spec)
        (workspace_path / "submission").mkdir(exist_ok=True)
    elif options.contract_closure_budget_control:
        (workspace_path / "submission").mkdir(exist_ok=True)
    elif (
        options.contract_closure_gate
        or options.contract_closure_gate_lite
        or options.contract_closure_gate_lite_v1
        or options.contract_closure_gate_lite_rescue
        or options.contract_closure_gate_lite_rescue_plus
        or options.contract_closure_gate_v3
    ):
        from .contract_closure_gate import install_contract_closure_workspace

        install_contract_closure_workspace(
            workspace_path,
            metadata=metadata,
            lite=(
                options.contract_closure_gate_lite
                or options.contract_closure_gate_lite_v1
                or options.contract_closure_gate_lite_rescue
                or options.contract_closure_gate_lite_rescue_plus
                or options.contract_closure_gate_v3
            ),
            frozen_v1=options.contract_closure_gate_lite_v1,
            rescue=options.contract_closure_gate_lite_rescue,
            rescue_plus=options.contract_closure_gate_lite_rescue_plus,
            v3=options.contract_closure_gate_v3,
        )
    else:
        (workspace_path / "submission").mkdir(exist_ok=True)
    task_file = workspace_path / "TASK.md"
    if get_spec_status(metadata) == SPEC_STATUS_COMPLIANT:
        if is_contract_only(options):
            task_markdown = render_contract_only_agent_workspace_task(
                metadata,
                mount_public_tests=options.mount_public_tests,
                source_entrypoints=(
                    _source_entrypoints_from_metadata(metadata)
                    if options.expose_source_hints
                    else None
                ),
            )
        else:
            task_markdown = render_agent_workspace_task(
                metadata,
                mount_public_tests=options.mount_public_tests,
                source_entrypoints=(
                    _source_entrypoints_from_metadata(metadata)
                    if options.expose_source_hints
                    else None
                ),
            )
    else:
        task_markdown = build_task_prompt(redacted_metadata, ablation=options)
    if options.td_cognition:
        task_markdown = (
            task_markdown.rstrip()
            + "\n\n## TD-Cognition Phase 1\n\n"
            + phase1_task_appendix()
        )
    elif options.exec_contract:
        from .exec_contract import phase1_task_appendix as exec_phase1_appendix

        task_markdown = (
            task_markdown.rstrip()
            + "\n\n## Execution-Guided Contract\n\n"
            + exec_phase1_appendix(variant=options.exec_contract_variant)
        )
    elif options.self_contract:
        from .self_contract import author_task_appendix

        task_markdown = (
            task_markdown.rstrip()
            + "\n\n## Self-Authored Contract Phase A\n\n"
            + author_task_appendix()
        )
    elif options.test_first_lift:
        from .test_first_lift import task_appendix as tfl_appendix

        task_markdown = (
            task_markdown.rstrip()
            + "\n\n"
            + tfl_appendix()
        )
    elif options.contract_closure_budget_control:
        from .contract_closure_budget_control import task_appendix as control_appendix

        task_markdown = task_markdown.rstrip() + "\n\n" + control_appendix()
    elif options.pre_submit_contract_audit:
        from .pre_submit_contract_audit import task_appendix as audit_appendix

        task_markdown = task_markdown.rstrip() + "\n\n" + audit_appendix()
    elif options.spec_adversarial_self_test:
        from .spec_adversarial import task_appendix as spec_adversarial_appendix

        task_markdown = (
            task_markdown.rstrip() + "\n\n" + spec_adversarial_appendix()
        )
    elif options.obligation_guided:
        from .obligation_guided import task_appendix as obligation_guided_appendix

        task_markdown = (
            task_markdown.rstrip() + "\n\n" + obligation_guided_appendix()
        )
    elif options.cgvl:
        from .cgvl import task_appendix as cgvl_appendix

        task_markdown = task_markdown.rstrip() + "\n\n" + cgvl_appendix()
    elif (
        options.contract_closure_gate
        or options.contract_closure_gate_lite
        or options.contract_closure_gate_lite_v1
        or options.contract_closure_gate_lite_rescue
        or options.contract_closure_gate_lite_rescue_plus
        or options.contract_closure_gate_v3
    ):
        from .contract_closure_gate import task_appendix as closure_appendix

        task_markdown = task_markdown.rstrip() + "\n\n" + closure_appendix(
            lite=(
                options.contract_closure_gate_lite
                or options.contract_closure_gate_lite_v1
                or options.contract_closure_gate_lite_rescue
                or options.contract_closure_gate_lite_rescue_plus
                or options.contract_closure_gate_v3
            ),
            frozen_v1=options.contract_closure_gate_lite_v1,
            rescue=options.contract_closure_gate_lite_rescue,
            rescue_plus=options.contract_closure_gate_lite_rescue_plus,
            v3=options.contract_closure_gate_v3,
        )
    task_file.write_text(task_markdown, encoding="utf-8")
    if not options.expose_source_hints:
        leaks = audit_no_hint_workspace(workspace_path)
        if leaks:
            raise ValueError(
                "No-Hint Main workspace contains source-location metadata: "
                + ", ".join(leaks)
            )
    if is_contract_only(options):
        assert_contract_only_workspace(workspace_path)
    return task_file


def redact_task_metadata(
    metadata: dict[str, Any],
    *,
    expose_source_hints: bool = False,
) -> dict[str, Any]:
    """Return the metadata subset that is safe and useful for an agent."""

    environment = metadata.get("environment") if isinstance(metadata.get("environment"), dict) else {}
    feature = metadata.get("feature") if isinstance(metadata.get("feature"), dict) else {}
    if get_spec_status(metadata) == SPEC_STATUS_COMPLIANT:
        # The generated TASK is the sole Agent-visible functional contract.
        # Legacy feature prose can repeat upstream symbols even after the
        # dedicated entrypoint fields are removed.
        feature_payload: dict[str, Any] = {}
        if expose_source_hints:
            feature_payload["source_entrypoints"] = (
                _source_entrypoints_from_metadata(metadata)
            )
    else:
        feature_payload = dict(feature)
    if not expose_source_hints:
        for key in (
            "source_entrypoints",
            "source_hints",
            "entrypoints",
            "repo_files",
            "source_files",
            "target_files",
            "implementation_hints",
        ):
            feature_payload.pop(key, None)
    language = str(metadata.get("language", "python"))
    environment_payload: dict[str, Any] = {
        "network": environment.get("network", False),
        "timeout_seconds": environment.get("timeout_seconds", 0),
        "forbidden_imports": environment.get("forbidden_imports", []),
    }
    if language == "go":
        environment_payload.update(
            {
                "go": environment.get("go", ""),
                "cgo_enabled": environment.get("cgo_enabled", False),
                "module_path": environment.get("module_path", "featurelifted"),
            }
        )
    else:
        environment_payload.update(
            {
                "python": environment.get("python", ""),
                "dependency_lock": environment.get("dependency_lock", "requirements.lock"),
                "allowed_dependencies": environment.get("allowed_dependencies", []),
                "forbidden_dependencies": environment.get("forbidden_dependencies", []),
            }
        )
    return {
        "task_id": metadata.get("task_id", ""),
        "language": language,
        "source": metadata.get("source", {}),
        "feature": feature_payload,
        "output": metadata.get("output", {}),
        "environment": environment_payload,
    }


def _is_python_main_task(task_path: Path) -> bool:
    return (
        task_path.parent.name == "tasks"
        and task_path.parent.parent.name == "benchmark"
        and (task_path / "metadata.json").is_file()
    )


def _source_entrypoints_from_metadata(metadata: dict[str, Any]) -> list[str]:
    """Return frozen private source hints for the explicit Entrypoint-Hint arm."""

    candidates: list[Any] = []
    evaluation_spec = (
        metadata.get("evaluation_spec")
        if isinstance(metadata.get("evaluation_spec"), dict)
        else {}
    )
    public_spec = (
        metadata.get("public_spec")
        if isinstance(metadata.get("public_spec"), dict)
        else {}
    )
    feature = metadata.get("feature") if isinstance(metadata.get("feature"), dict) else {}
    candidates.extend(
        (
            evaluation_spec.get("source_entrypoints"),
            public_spec.get("source_entrypoints"),
            feature.get("source_entrypoints"),
            metadata.get("source_hints"),
        )
    )
    for candidate in candidates:
        if not isinstance(candidate, list):
            continue
        values = [str(item) for item in candidate if isinstance(item, str) and item.strip()]
        if values:
            return values
    return []


def audit_no_hint_workspace(workspace_dir: str | Path) -> list[str]:
    """Return Agent-facing source-hint leaks outside the upstream repository."""

    workspace = Path(workspace_dir)
    leaks: list[str] = []
    metadata_path = workspace / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    banned_keys = {
        "source_entrypoints",
        "source_hints",
        "entrypoints",
        "repo_files",
        "source_files",
        "target_files",
        "implementation_hints",
    }

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key in banned_keys:
                    leaks.append(child_path)
                walk(item, child_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(metadata, "metadata")
    task_path = workspace / "TASK.md"
    try:
        task_text = task_path.read_text(encoding="utf-8")
    except OSError:
        task_text = ""
    if "Source Entrypoints — Entrypoint-Hint Ablation" in task_text:
        leaks.append("TASK.md:entrypoint_hint_section")
    return sorted(set(leaks))


def build_task_prompt(
    metadata: dict[str, Any],
    *,
    ablation: AblationOptions | None = None,
) -> str:
    """Build the task prompt given to the agent."""

    options = ablation or AblationOptions()
    if str(metadata.get("language", "python")) == "go":
        return _build_go_task_prompt(metadata, ablation=options)
    return _build_python_task_prompt(metadata, ablation=options)


def _shared_task_prompt_sections(metadata: dict[str, Any]) -> dict[str, str]:
    feature = metadata.get("feature", {}) if isinstance(metadata.get("feature"), dict) else {}
    output = metadata.get("output", {}) if isinstance(metadata.get("output"), dict) else {}
    entanglement = (
        metadata.get("entanglement", {}) if isinstance(metadata.get("entanglement"), dict) else {}
    )
    environment = (
        metadata.get("environment", {}) if isinstance(metadata.get("environment"), dict) else {}
    )
    source = metadata.get("source", {}) if isinstance(metadata.get("source"), dict) else {}
    forbidden_import_names = [
        item.strip("- ").strip()
        for item in (environment.get("forbidden_imports") or [])
        if isinstance(item, str) and item.strip()
    ]
    forbidden_grep = " ".join(forbidden_import_names[:5]) or "original package names"
    return {
        "task_id": str(metadata.get("task_id", "")),
        "tags": _format_list(metadata.get("tags", [])),
        "entanglement_types": _format_list(entanglement.get("types", [])),
        "entanglement_signals": _format_list(entanglement.get("signals", [])),
        "included": _format_list(feature.get("included_behaviors", [])),
        "excluded": _format_list(feature.get("excluded_behaviors", [])),
        "entrypoints": _format_list(feature.get("source_entrypoints", [])),
        "forbidden_imports": _format_list(environment.get("forbidden_imports", [])),
        "forbidden_grep": forbidden_grep,
        "feature_name": str(feature.get("name", "")),
        "feature_description": str(feature.get("description", "")),
        "difficulty": str(metadata.get("difficulty", "")),
        "entanglement_level": str(entanglement.get("level", "")),
        "entanglement_description": str(entanglement.get("description", "")),
        "output_package": str(output.get("package", "featurelifted")),
        "output_import": str(output.get("import", "")),
        "output_callable": str(output.get("callable", "")),
        "output_signature": str(output.get("signature", "")),
        "source_name": str(source.get("name", "")),
        "source_url": str(source.get("url", "")),
        "source_commit": str(source.get("commit", "")),
        "source_license": str(source.get("license", "")),
    }


def _source_hint_prompt_section(
    sections: dict[str, str],
    options: AblationOptions,
) -> str:
    if not options.expose_source_hints:
        return ""
    return (
        "## Source Entrypoints — Entrypoint-Hint Ablation\n\n"
        f"{sections['entrypoints']}\n"
    )


def _build_go_task_prompt(
    metadata: dict[str, Any],
    *,
    ablation: AblationOptions | None = None,
) -> str:
    options = ablation or AblationOptions()
    sections = _shared_task_prompt_sections(metadata)
    environment = (
        metadata.get("environment", {}) if isinstance(metadata.get("environment"), dict) else {}
    )
    output = metadata.get("output", {}) if isinstance(metadata.get("output"), dict) else {}
    module_path = str(output.get("module") or environment.get("module_path", "featurelifted"))
    package_name = sections["output_package"]
    symbols = _format_list(output.get("symbols", []))
    go_version = str(environment.get("go", "1.22"))
    parts = [
        f"# FeatureLiftBench Go Task: {sections['task_id']}\n\n"
        "You are in a FeatureLiftBench agent workspace. Decouple the requested feature from "
        f"`repo/` into a standalone Go module under `submission/` (package `{package_name}`).\n\n"
    ]
    parts.append(_go_howto_section(sections, module_path, package_name, go_version, options))
    parts.append(_go_workspace_section(options))
    if options.prompt_style == "standard":
        localization = (
            "- Start from the provided source entrypoints, then follow helpers, constants, "
            "tables, and error handling needed for the public contract.\n"
            if options.expose_source_hints
            else "- Search the complete repository from the functional contract and required "
            "output API; locate the implementation and its supporting closure yourself.\n"
        )
        parts.append(
            "## Closure Discipline\n\n"
            "- Treat the target as a real extracted feature, not a toy rewrite for public tests.\n"
            + localization
            + "- Remove tests, CLI, and unrelated subsystems unless the feature spec needs them.\n\n"
        )
    parts.append(
        "## Source\n\n"
        f"- Name: {sections['source_name']}\n"
        f"- URL: {sections['source_url']}\n"
        f"- Commit: {sections['source_commit']}\n"
        f"- License: {sections['source_license']}\n\n"
        "## Target Feature\n\n"
        f"- Name: {sections['feature_name']}\n"
        f"- Difficulty: {sections['difficulty']}\n"
        f"- Tags:\n{sections['tags']}\n"
        f"- Description: {sections['feature_description']}\n"
        + _source_hint_prompt_section(sections, options)
        + f"- Included behaviors:\n{sections['included']}\n"
        f"- Excluded behaviors:\n{sections['excluded']}\n"
    )
    if options.prompt_style == "standard":
        parts.append(
            "## Entanglement Context\n\n"
            f"- Level: {sections['entanglement_level']}\n"
            f"- Types:\n{sections['entanglement_types']}\n"
            f"- Description: {sections['entanglement_description']}\n"
            f"- Signals:\n{sections['entanglement_signals']}\n"
        )
    parts.append(
        "## Required Output API\n\n"
        f"- Package: `{sections['output_package']}`\n"
        f"- Import: `{sections['output_import']}`\n"
        f"- Symbols:\n{symbols}\n"
        + (
            f"- Callable: `{sections['output_callable']}`\n"
            f"- Signature: `{sections['output_signature']}`\n"
            if sections["output_callable"] or sections["output_signature"]
            else ""
        )
        + "\n"
        "## Constraints\n\n"
        "- The final answer must be files under `submission/`.\n"
        "- Do not modify `repo/`"
        + (" or `public_tests/`" if options.mount_public_tests else "")
        + " as your final deliverable.\n"
        "- Do not import the original source module at runtime.\n"
        "- **Forbidden imports are a hard gate.**\n"
        "- **Scoring:** Functional Pass@1 is the primary gate. Compactness is "
        "reported independently relative to the frozen reference implementation; "
        "whole-repo copying remains visible in that secondary metric.\n"
        f"- Forbidden imports:\n{sections['forbidden_imports']}\n\n"
        + _finish_footer(options)
    )
    return "".join(parts)


def _build_python_task_prompt(
    metadata: dict[str, Any],
    *,
    ablation: AblationOptions | None = None,
) -> str:
    options = ablation or AblationOptions()
    sections = _shared_task_prompt_sections(metadata)
    environment = (
        metadata.get("environment", {}) if isinstance(metadata.get("environment"), dict) else {}
    )
    allowed_dependencies = _format_list(environment.get("allowed_dependencies", []))
    forbidden_dependencies = _format_list(environment.get("forbidden_dependencies", []))
    if is_contract_only(options):
        from .source_ablation import contract_only_python_intro

        parts = [contract_only_python_intro(sections)]
    else:
        parts = [
            f"# FeatureLiftBench Task: {sections['task_id']}\n\n"
            "You are in a FeatureLiftBench agent workspace. Decouple the requested feature from "
            "`repo/` into a standalone, installable Python package under `submission/`.\n\n"
        ]
    parts.append(_python_howto_section(sections, options))
    parts.append(_python_workspace_section(options))
    if options.prompt_style == "standard":
        if is_contract_only(options):
            from .source_ablation import contract_only_closure_localization

            localization = contract_only_closure_localization()
        elif options.expose_source_hints:
            localization = (
                "- Start from the provided source entrypoints, then follow imports, helpers, "
                "constants, data files, exceptions, and resources needed by the contract.\n"
            )
        else:
            localization = (
                "- Search the complete repository from the functional contract and required "
                "output API; locate the implementation and its supporting closure yourself.\n"
            )
        parts.append(
            "## Closure Discipline\n\n"
            "- Treat the target as a real extracted feature, not a toy rewrite for public tests.\n"
            + localization
            + "- Every copied file should support target behavior, public API compatibility, an "
            "exception/type/resource, or a transitive helper used by that behavior.\n"
            "- Remove tests, docs, CLI, network/runtime subsystems, and unrelated adapters unless "
            "the feature specification needs them.\n"
            "- After covering included behaviors and the Required Output API, prune unrelated code "
            "before submitting.\n\n"
        )
    parts.append(
        "## Source\n\n"
        f"- Name: {sections['source_name']}\n"
        f"- URL: {sections['source_url']}\n"
        f"- Commit: {sections['source_commit']}\n"
        f"- License: {sections['source_license']}\n\n"
        "## Target Feature\n\n"
        f"- Name: {sections['feature_name']}\n"
        f"- Difficulty: {sections['difficulty']}\n"
        f"- Tags:\n{sections['tags']}\n"
        f"- Description: {sections['feature_description']}\n"
        + _source_hint_prompt_section(sections, options)
        + f"- Included behaviors:\n{sections['included']}\n"
        f"- Excluded behaviors:\n{sections['excluded']}\n"
    )
    if options.prompt_style == "standard":
        parts.append(
            "## Entanglement Context\n\n"
            f"- Level: {sections['entanglement_level']}\n"
            f"- Types:\n{sections['entanglement_types']}\n"
            f"- Description: {sections['entanglement_description']}\n"
            f"- Signals:\n{sections['entanglement_signals']}\n"
        )
    if is_contract_only(options):
        implementation_scope = contract_only_implementation_scope()
        repo_constraint = (
            "- The upstream source repository is not present; do not search for it.\n"
        )
    elif options.expose_source_hints:
        implementation_scope = (
            "- Implementation scope: use the explicitly provided **Source entrypoints** to "
            "locate code in `repo/`; the import line lists the public surface your package "
            "must expose.\n\n"
        )
        repo_constraint = (
            "- Do not modify `repo/`"
            + (" or `public_tests/`" if options.mount_public_tests else "")
            + " as your final deliverable.\n"
        )
    else:
        implementation_scope = (
            "- Implementation scope: locate the upstream implementation yourself from "
            "the functional contract and required output API; the import line lists the "
            "public surface your package must expose.\n\n"
        )
        repo_constraint = (
            "- Do not modify `repo/`"
            + (" or `public_tests/`" if options.mount_public_tests else "")
            + " as your final deliverable.\n"
        )
    parts.append(
        "## Required Output API\n\n"
        f"- Package: `{sections['output_package']}`\n"
        f"- Import: `{sections['output_import']}`\n"
        f"- Callable: `{sections['output_callable']}`\n"
        f"- Signature: `{sections['output_signature']}`\n"
        + implementation_scope
        + "## Constraints\n\n"
        "- The final answer must be files under `submission/`.\n"
        + repo_constraint
        + "- Do not import from the original source package or rely on the original repo path at runtime.\n"
        "- Do not symlink or copy hidden/evaluator files. They are intentionally unavailable.\n"
        "- Keep only behavior-relevant code and dependencies needed for the target feature; "
        "prefer a compact closure, but do not remove helpers/resources required by edge cases.\n"
        "- **Forbidden imports are a hard gate:** if your submission imports a forbidden name, "
        "`functional_gate` is 0 even when tests pass.\n"
        "- **Scoring:** Functional Pass@1 is the primary gate. Compactness is "
        "reported independently relative to the frozen reference implementation; "
        "extract only what the feature needs.\n"
        f"- Allowed dependencies:\n{allowed_dependencies}\n"
        f"- Forbidden dependencies:\n{forbidden_dependencies}\n"
        f"- Forbidden imports:\n{sections['forbidden_imports']}\n\n"
        + _finish_footer(options)
    )
    return "".join(parts)


def _python_howto_section(sections: dict[str, str], options: AblationOptions) -> str:
    if is_contract_only(options):
        from .source_ablation import contract_only_python_howto

        return contract_only_python_howto(sections, options)
    if options.prompt_style == "short":
        lines = [
            "## How to work\n\n",
            "1. Implement every symbol in **Required Output API** and every included behavior "
            "from `repo/` into `submission/featurelifted/`.\n",
            "2. Rewrite imports so runtime code uses `featurelifted` only.\n",
            f"3. Grep for forbidden imports before submit, e.g. "
            f"`grep -R \"import \" submission/ | grep -E '({sections['forbidden_grep']})'`.\n",
            "4. Verify `submission/featurelifted/` exists, then submit.\n\n",
        ]
        if not options.mount_public_tests:
            lines.insert(
                3,
                "3. Benchmark evaluator tests are not available; inspect upstream tests under "
                "`repo/` when present or write your own tests.\n",
            )
            # renumber roughly - keep simple
            lines = [
                "## How to work\n\n",
                "1. Implement every symbol in **Required Output API** and every included behavior "
                "from `repo/` into `submission/featurelifted/`.\n",
                "2. Rewrite imports so runtime code uses `featurelifted` only.\n",
                "3. Benchmark evaluator tests are not available; inspect upstream tests under "
                "`repo/` when present or write your own tests.\n",
                f"4. Grep for forbidden imports before submit, e.g. "
                f"`grep -R \"import \" submission/ | grep -E '({sections['forbidden_grep']})'`.\n",
                "5. Verify `submission/featurelifted/` exists, then submit.\n\n",
            ]
        return "".join(lines)

    localization_step = (
        "1. Read the provided `source entrypoints` and the full **Required Output API** "
        "below — implement every listed import path, not just the primary callable.\n"
        if options.expose_source_hints
        else "1. Use the functional contract and **Required Output API** to search `repo/` "
        "and locate the upstream implementation yourself; implement every listed output path.\n"
    )
    if options.mount_public_tests:
        return (
            "## How to work\n\n"
            + localization_step
            + "2. Copy the smallest **behavior-complete** implementation closure from `repo/` "
            "into `submission/featurelifted/`.\n"
            "3. Rewrite imports so runtime code uses `featurelifted` only — never the original package.\n"
            f"4. Before submitting, grep your submission for forbidden imports, e.g. "
            f"`grep -R \"import \" submission/ | grep -E '({sections['forbidden_grep']})'` — any match fails evaluation.\n"
            "5. Run `pytest public_tests/` in the workspace and fix failures.\n"
            "6. **Public tests passing does not mean you are done.** The evaluator also runs hidden tests "
            "and stricter checks you cannot see here.\n"
            "7. Before submitting, verify your package is under `submission/featurelifted/`, e.g. "
            "`test -d submission/featurelifted && ls submission/featurelifted | head`.\n"
            "8. Do **not** put your package in `featurelifted/` at the workspace root — only "
            "`submission/featurelifted/` counts.\n"
            "9. When confident, submit with the command at the bottom.\n\n"
        )
    return (
        "## How to work\n\n"
        + localization_step
        + "2. Copy the smallest **behavior-complete** implementation closure from `repo/` "
        "into `submission/featurelifted/`.\n"
        "3. Rewrite imports so runtime code uses `featurelifted` only — never the original package.\n"
        "4. **Benchmark evaluator tests are not mounted.** Inspect relevant upstream tests, docs, "
        "and examples under `repo/` when present; adapt them or write your own tests for the submission.\n"
        "5. Implement against the complete public contract; do not attempt to locate evaluator tests.\n"
        f"6. Before submitting, grep your submission for forbidden imports, e.g. "
        f"`grep -R \"import \" submission/ | grep -E '({sections['forbidden_grep']})'` — any match fails evaluation.\n"
        "7. Before submitting, verify your package is under `submission/featurelifted/`, e.g. "
        "`test -d submission/featurelifted && ls submission/featurelifted | head`.\n"
        "8. Do **not** put your package in `featurelifted/` at the workspace root — only "
        "`submission/featurelifted/` counts.\n"
        "9. When confident, submit with the command at the bottom.\n\n"
    )


def _python_workspace_section(options: AblationOptions) -> str:
    if is_contract_only(options):
        from .source_ablation import contract_only_python_workspace

        return contract_only_python_workspace()
    lines = [
        "## Workspace\n\n",
        "- `repo/`: source repository snapshot for the fixed commit.\n",
    ]
    if options.mount_public_tests:
        lines.append("- `public_tests/`: tests you may run while developing.\n")
    else:
        lines.append(
            "- Benchmark-authored evaluator tests are not provided. Upstream tests/docs/examples "
            "inside `repo/` remain visible, and you may write and run your own tests.\n"
        )
    lines.extend(
        [
            "- `requirements.lock`: locked third-party runtime dependencies allowed by the task.\n",
            "- `metadata.json`: redacted task metadata. Hidden tests and evaluator internals are not present.\n",
            "- `submission/`: write your final package here.\n\n",
        ]
    )
    return "".join(lines)


def _go_howto_section(
    sections: dict[str, str],
    module_path: str,
    package_name: str,
    go_version: str,
    options: AblationOptions,
) -> str:
    if options.prompt_style == "short":
        body = (
            "## How to work\n\n"
            "1. Implement Required Output API symbols from `repo/` into `submission/`.\n"
            f"2. Add `submission/go.mod` with `module {module_path}` and `go {go_version}`.\n"
            f"3. Rewrite imports to package `{package_name}` only.\n"
        )
        if not options.mount_public_tests:
            body += (
                "4. Benchmark evaluator tests are unavailable; inspect upstream tests under "
                "`repo/` or write your own.\n5. Grep forbidden imports, then submit.\n\n"
            )
        else:
            body += "4. Grep forbidden imports, then submit.\n\n"
        return body
    localization_step = (
        "1. Read the provided `source entrypoints` and the full **Required Output API** below.\n"
        if options.expose_source_hints
        else "1. Use the functional contract and **Required Output API** to search `repo/` "
        "and locate the upstream implementation yourself.\n"
    )
    if options.mount_public_tests:
        return (
            "## How to work\n\n"
            + localization_step
            + "2. Copy the smallest **behavior-complete** implementation closure from `repo/` "
            f"into `submission/` as package `{package_name}`.\n"
            f"3. Add `submission/go.mod` with `module {module_path}` and `go {go_version}`.\n"
            f"4. Rewrite package names/imports so runtime code uses `{package_name}` only — "
            "never the original module path.\n"
            f"5. Before submitting, grep your submission for forbidden imports, e.g. "
            f"`grep -R '\"' submission/*.go | grep -E '({sections['forbidden_grep']})'` — "
            "any match fails evaluation.\n"
            "6. Run `./run_public_tests.sh` in the workspace (the isolated equivalent of "
            "`go test ./public_tests/...`) "
            "and fix failures.\n"
            "7. **Public tests passing does not mean you are done.** Hidden tests and extraction "
            "scoring apply after submit.\n"
            "8. Write all deliverables under `submission/` only (`*.go` + `go.mod`).\n"
            "9. When confident, submit with the command at the bottom.\n\n"
        )
    return (
        "## How to work\n\n"
        + localization_step
        + "2. Copy the smallest **behavior-complete** implementation closure from `repo/` "
        f"into `submission/` as package `{package_name}`.\n"
        f"3. Add `submission/go.mod` with `module {module_path}` and `go {go_version}`.\n"
        f"4. Rewrite package names/imports so runtime code uses `{package_name}` only — "
        "never the original module path.\n"
        "5. **Benchmark evaluator tests are not mounted.** Inspect upstream tests/docs/examples "
        "under `repo/` when present, or write and run your own tests.\n"
        "6. Implement from the complete public contract; do not seek evaluator tests.\n"
        f"7. Before submitting, grep your submission for forbidden imports, e.g. "
        f"`grep -R '\"' submission/*.go | grep -E '({sections['forbidden_grep']})'` — "
        "any match fails evaluation.\n"
        "8. Write all deliverables under `submission/` only (`*.go` + `go.mod`).\n"
        "9. When confident, submit with the command at the bottom.\n\n"
    )


def _go_workspace_section(options: AblationOptions) -> str:
    lines = [
        "## Workspace\n\n",
        "- `repo/`: source repository snapshot for the fixed commit.\n",
    ]
    if options.mount_public_tests:
        lines.extend(
            [
                "- `public_tests/`: tests you may run while developing.\n",
                "- `go.mod`: eval harness module (add `replace` for your submission).\n",
                "- `run_public_tests.sh`: isolated public-test runner for your submission.\n",
            ]
        )
    else:
        lines.extend(
            [
                "- Benchmark evaluator tests are not provided. Upstream repository tests remain "
                "visible under `repo/` when present.\n",
                "- `go.mod`: eval harness module (add `replace` for your submission).\n",
            ]
        )
    lines.extend(
        [
            "- `metadata.json`: redacted task metadata. Hidden tests are not present.\n",
            "- `submission/`: write your final Go module here.\n\n",
        ]
    )
    return "".join(lines)


def _finish_footer(options: AblationOptions) -> str:
    if options.mount_public_tests:
        preface = (
            "You may run the public tests during development. The evaluator will later run public and "
            "hidden tests in a clean environment. When finished, run:\n\n"
        )
    else:
        preface = (
            "Benchmark evaluator tests are unavailable during development. The evaluator runs both "
            "test tiers in a clean environment only after submit. When finished, run:\n\n"
        )
    return (
        preface
        + "```bash\n"
        + "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n"
        + "```\n"
    )



def _copy_path(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
    )
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_submission(src: Path, dst: Path) -> None:
    _reset_dir(dst)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _reset_dir(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _has_submission_files(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(child.name != ".gitkeep" for child in path.iterdir())


def _package_has_python_files(path: Path) -> bool:
    return path.is_dir() and any(path.rglob("*.py"))


def _recover_misplaced_submission(workspace_dir: Path, submission_dir: Path) -> dict[str, Any] | None:
    """Collect agent output from known misplaced workspace paths into submission/."""

    if _has_submission_files(submission_dir):
        return None

    recovery_sources: list[str] = []
    try:
        featurelifted_root = workspace_dir / "featurelifted"
        if _package_has_python_files(featurelifted_root):
            dest = submission_dir / "featurelifted"
            submission_dir.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(featurelifted_root, dest, dirs_exist_ok=True)
            recovery_sources.append("workspace/featurelifted")

        pyproject_root = workspace_dir / "pyproject.toml"
        if pyproject_root.is_file() and not (submission_dir / "pyproject.toml").is_file():
            submission_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pyproject_root, submission_dir / "pyproject.toml")
            recovery_sources.append("workspace/pyproject.toml")

        go_files = [path for path in workspace_dir.glob("*.go") if path.is_file()]
        workspace_go_mod = workspace_dir / "go.mod"
        if go_files or workspace_go_mod.is_file():
            submission_dir.mkdir(parents=True, exist_ok=True)
            for path in go_files:
                dest = submission_dir / path.name
                if not dest.is_file():
                    shutil.copy2(path, dest)
                    recovery_sources.append(f"workspace/{path.name}")
            if workspace_go_mod.is_file() and not (submission_dir / "go.mod").is_file():
                shutil.copy2(workspace_go_mod, submission_dir / "go.mod")
                recovery_sources.append("workspace/go.mod")
    except OSError as exc:
        return {
            "recovered": False,
            "recovery_sources": recovery_sources,
            "message": f"submission recovery failed: {exc}",
        }

    if not recovery_sources or not _has_submission_files(submission_dir):
        return None

    sources_text = ", ".join(recovery_sources)
    return {
        "recovered": True,
        "recovery_sources": recovery_sources,
        "message": (
            f"recovered submission from misplaced paths ({sources_text}); "
            "agent wrote outside workspace/submission"
        ),
    }


def _missing_submission_diagnostic(workspace_dir: Path) -> str:
    if _package_has_python_files(workspace_dir / "featurelifted"):
        return (
            "workspace/featurelifted exists but submission recovery did not populate "
            "workspace/submission"
        )
    if any(workspace_dir.glob("*.go")):
        return (
            "workspace/*.go exists but submission recovery did not populate "
            "workspace/submission"
        )
    return "no submission files and no recoverable misplaced paths found under workspace/"


def _write_agent_logs(agent_output_dir: Path, result: Any) -> None:
    agent_output_dir.mkdir(parents=True, exist_ok=True)
    (agent_output_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (agent_output_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")


def _collect_agent_usage(agent_name: str, agent_output_dir: Path) -> dict[str, Any]:
    """Collect token and step usage without making usage availability affect grading."""

    usage_path = agent_output_dir / "usage.json"
    if usage_path.is_file():
        return _parse_agent_usage_json(usage_path)

    normalized = agent_name.strip().lower().replace("_", "-")
    if normalized in {"mini", "mini-swe-agent", "minisweagent"}:
        return _parse_mini_trajectory_usage(agent_output_dir / "trajectory.json")

    return _unavailable_agent_usage(usage_path, "usage.json not found")


def _parse_agent_usage_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return _unavailable_agent_usage(path, f"cannot read usage.json: {exc}")
    except json.JSONDecodeError as exc:
        return _unavailable_agent_usage(path, f"invalid usage.json: {exc}")
    if not isinstance(data, dict):
        return _unavailable_agent_usage(path, "usage.json must contain a JSON object")
    return _sanitize_usage_payload(data, path)


def _aggregate_message_usage(messages: list[Any]) -> dict[str, int]:
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    saw_prompt = False
    saw_completion = False
    saw_total = False

    for message in messages:
        if not isinstance(message, dict):
            continue
        extra = message.get("extra")
        if not isinstance(extra, dict):
            continue
        response = extra.get("response")
        if not isinstance(response, dict):
            continue
        usage = response.get("usage")
        if not isinstance(usage, dict):
            continue

        prompt = _int_metric(usage.get("prompt_tokens"))
        if prompt is not None:
            prompt_tokens += prompt
            saw_prompt = True
        completion = _int_metric(usage.get("completion_tokens"))
        if completion is not None:
            completion_tokens += completion
            saw_completion = True
        total = _int_metric(usage.get("total_tokens"))
        if total is not None:
            total_tokens += total
            saw_total = True

    aggregated: dict[str, int] = {}
    if saw_prompt:
        aggregated["prompt_tokens"] = prompt_tokens
    if saw_completion:
        aggregated["completion_tokens"] = completion_tokens
    if saw_prompt or saw_completion:
        aggregated["total_tokens"] = prompt_tokens + completion_tokens
    elif saw_total:
        aggregated["total_tokens"] = total_tokens
    return aggregated


def _parse_mini_trajectory_usage(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _unavailable_agent_usage(path, "trajectory.json not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return _unavailable_agent_usage(path, f"cannot read trajectory.json: {exc}")
    except json.JSONDecodeError as exc:
        return _unavailable_agent_usage(path, f"invalid trajectory.json: {exc}")
    if not isinstance(data, dict):
        return _unavailable_agent_usage(path, "trajectory.json must contain a JSON object")

    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    model_stats = info.get("model_stats") if isinstance(info.get("model_stats"), dict) else {}
    messages = data.get("messages")

    usage: dict[str, Any] = {"available": True, "source": str(path)}
    if isinstance(messages, list):
        usage["total_messages"] = len(messages)
        usage["assistant_steps"] = sum(
            1
            for message in messages
            if isinstance(message, dict) and message.get("role") == "assistant"
        )

    for key in (
        "api_calls",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "trace_tokens",
        "billed_tokens",
    ):
        value = _int_metric(model_stats.get(key))
        if value is not None:
            usage[key] = value

    if isinstance(messages, list):
        aggregated = _aggregate_message_usage(messages)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key not in usage and key in aggregated:
                usage[key] = aggregated[key]

    exit_status = info.get("exit_status")
    if isinstance(exit_status, str):
        usage["exit_status"] = exit_status
    if len(usage) <= 2:
        return _unavailable_agent_usage(path, "trajectory.json did not contain usage metrics")
    return usage


def _sanitize_usage_payload(data: dict[str, Any], source: Path) -> dict[str, Any]:
    usage: dict[str, Any] = {"available": True, "source": str(source)}
    for key in ("schema_version", "agent_name", "model"):
        value = data.get(key)
        if isinstance(value, str):
            usage[key] = value
    for key in USAGE_SUM_FIELDS:
        value = _int_metric(data.get(key))
        if value is not None:
            usage[key] = value
    cache_available = data.get("prompt_cache_accounting_available")
    if isinstance(cache_available, bool):
        usage["prompt_cache_accounting_available"] = cache_available
    exit_status = data.get("exit_status")
    if isinstance(exit_status, str):
        usage["exit_status"] = exit_status
    context_audit = data.get("context_audit")
    if isinstance(context_audit, dict):
        usage["context_audit"] = dict(context_audit)
    tool_summary = data.get("tool_summary")
    if isinstance(tool_summary, dict):
        usage["tool_summary"] = dict(tool_summary)
    if len(usage) <= 2:
        return _unavailable_agent_usage(source, "usage.json did not contain usage metrics")
    return usage


def _sum_agent_usage(runs: list[dict[str, Any]]) -> dict[str, Any]:
    usages: list[dict[str, Any]] = []
    for run in runs:
        usage = effective_agent_usage_for_run(run)
        if usage.get("available") is True:
            usages.append(usage)

    totals: dict[str, Any] = {
        "available_runs": len(usages),
        "missing_runs": len(runs) - len(usages),
    }
    for key in USAGE_SUM_FIELDS:
        totals[key] = sum(
            value for usage in usages if isinstance((value := usage.get(key)), int)
        )
    totals["prompt_cache_accounting_available_runs"] = sum(
        usage.get("prompt_cache_accounting_available") is True for usage in usages
    )
    cache_total = totals["prompt_cache_hit_tokens"] + totals["prompt_cache_miss_tokens"]
    totals["prompt_cache_hit_rate"] = (
        totals["prompt_cache_hit_tokens"] / cache_total if cache_total > 0 else None
    )
    context_audits = [
        audit
        for usage in usages
        if isinstance((audit := usage.get("context_audit")), dict)
        and audit.get("available") is True
    ]
    if context_audits:
        totals["context_audit"] = {
            "available_runs": len(context_audits),
            "context_violation_runs": sum(
                audit.get("context_violation") is True for audit in context_audits
            ),
            "usage_unverified_runs": sum(
                audit.get("usage_unverified") is True for audit in context_audits
            ),
            "max_prompt_tokens_per_call": max(
                (_int_metric(audit.get("max_prompt_tokens_per_call")) or 0)
                for audit in context_audits
            ),
            "max_total_tokens_per_call": max(
                (_int_metric(audit.get("max_total_tokens_per_call")) or 0)
                for audit in context_audits
            ),
            "token_compression_runs": sum(
                audit.get("compression_mode") == "token" for audit in context_audits
            ),
            "condensation_events": sum(
                _int_metric(audit.get("condensation_events")) or 0
                for audit in context_audits
            ),
            "forgotten_event_count": sum(
                _int_metric(audit.get("forgotten_event_count")) or 0
                for audit in context_audits
            ),
        }
    tool_summaries = [
        summary
        for usage in usages
        if isinstance((summary := usage.get("tool_summary")), dict)
        and summary.get("available") is True
    ]
    if tool_summaries:
        summed_fields = (
            "total_actions",
            "success_actions",
            "failed_actions",
            "blocked_actions",
            "timeout_actions",
            "error_actions",
        )
        totals["tool_summary"] = {
            "available_runs": len(tool_summaries),
            "actions_enabled_runs": sum(
                summary.get("actions_enabled") is True for summary in tool_summaries
            ),
            "runs_with_failed_actions": sum(
                (_int_metric(summary.get("failed_actions")) or 0) > 0
                for summary in tool_summaries
            ),
            "final_check_failed_runs": sum(
                summary.get("final_check_status") == "failed" for summary in tool_summaries
            ),
            **{
                key: sum((_int_metric(summary.get(key)) or 0) for summary in tool_summaries)
                for key in summed_fields
            },
        }
    return totals


def _unavailable_agent_usage(source: Path, reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "source": str(source),
        "reason": reason,
    }


def _int_metric(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _test_path(metadata: dict[str, Any], key: str, default: str) -> str:
    tests = metadata.get("tests")
    if isinstance(tests, dict):
        value = tests.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def _dependency_lock(metadata: dict[str, Any]) -> str:
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        value = environment.get("dependency_lock")
        if isinstance(value, str) and value:
            return value
    return "requirements.lock"


def _format_list(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "- None"
    return "\n".join(f"- {item}" for item in value if isinstance(item, str))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
