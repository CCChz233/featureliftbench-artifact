"""Orchestrate setup / run / resume workflows from flb.local.toml."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .agent_runner import run_agent_on_path
from .local_config import (
    LocalConfig,
    RuntimePolicy,
    SuitePhase,
    SuitePreset,
    apply_local_overrides,
    load_local_agent_config,
    load_local_config,
    resolve_output_dir,
    resolve_runtime_policy,
    resolve_suite_preset,
    write_run_meta,
)
from .paths import REPO_ROOT, SCRIPTS_DIR

HARNESS_ROOT = REPO_ROOT / "harness"
PREFLIGHT_SCRIPT = SCRIPTS_DIR / "preflight.py"


@dataclass(frozen=True)
class WorkflowResult:
    output_dir: Path
    exit_code: int
    phase_results: tuple[dict[str, Any], ...]
    dry_run: bool


@contextmanager
def _env_overlay(updates: dict[str, str]) -> Iterator[None]:
    previous: dict[str, str | None] = {}
    for key, value in updates.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


@contextmanager
def _run_lock(output_dir: Path) -> Iterator[None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_dir = output_dir / ".run.lock"
    try:
        lock_dir.mkdir(exist_ok=False)
    except FileExistsError as exc:
        holder = ""
        pid_path = lock_dir / "pid"
        if pid_path.is_file():
            holder = pid_path.read_text(encoding="utf-8").strip()
        message = f"another suite run holds {lock_dir}"
        if holder:
            message += f" (pid {holder})"
        raise RuntimeError(message) from exc
    pid_path = lock_dir / "pid"
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    try:
        yield
    finally:
        pid_path.unlink(missing_ok=True)
        try:
            lock_dir.rmdir()
        except OSError:
            pass


def cmd_setup(
    *,
    config_path: Path | None = None,
    dry_run: bool = False,
) -> int:
    local_config = load_local_config(config_path)
    suite_preset = resolve_suite_preset(local_config)
    policy = resolve_runtime_policy(local_config)

    if dry_run:
        _print_dry_run_summary(local_config, suite_preset, policy, output_dir=None)
        return 0

    with _env_overlay(policy.env):
        code = _run_preflight(
            local_config,
            suite_preset,
            output_dir=REPO_ROOT / "experiments" / "smoke" / "preflight",
            llm_health_check=True,
        )
    if code == 0:
        _print_setup_summary(local_config, suite_preset, policy)
    return code


def cmd_run(
    *,
    config_path: Path | None = None,
    resume_dir: Path | None = None,
    suite: str | None = None,
    max_steps: int | None = None,
    workers: int | None = None,
    output_dir: str | None = None,
    dry_run: bool = False,
) -> WorkflowResult:
    local_config = apply_local_overrides(
        load_local_config(config_path),
        suite=suite,
        max_steps=max_steps,
        workers=workers,
        output_dir=output_dir,
    )
    suite_preset = resolve_suite_preset(local_config)
    policy = resolve_runtime_policy(local_config)
    resolved_output = resolve_output_dir(
        local_config,
        suite_preset=suite_preset,
        resume_dir=resume_dir,
    )

    if dry_run:
        _print_dry_run_summary(local_config, suite_preset, policy, output_dir=resolved_output)
        return WorkflowResult(
            output_dir=resolved_output,
            exit_code=0,
            phase_results=(),
            dry_run=True,
        )

    phase_results: list[dict[str, Any]] = []
    with _env_overlay(policy.env):
        preflight_code = _run_preflight(
            local_config,
            suite_preset,
            output_dir=resolved_output / "preflight",
            llm_health_check=True,
        )
        if preflight_code != 0:
            return WorkflowResult(
                output_dir=resolved_output,
                exit_code=preflight_code,
                phase_results=tuple(phase_results),
                dry_run=False,
            )

        with _run_lock(resolved_output):
            write_run_meta(
                resolved_output,
                local_config=local_config,
                suite_preset=suite_preset,
                resumed=resume_dir is not None,
            )
            if resume_dir is not None and suite_preset.name != "pilot5":
                _validate_resume(resolved_output, require_docker_eval=local_config.run.eval_docker)

            loaded = load_local_agent_config(local_config)
            worst_exit = 0

            for phase in suite_preset.phases:
                phase_output = (
                    resolved_output
                    if phase.output_subdir == "."
                    else resolved_output / phase.output_subdir
                )
                phase_exit = _run_phase(
                    local_config=local_config,
                    loaded_config=loaded,
                    phase=phase,
                    output_dir=phase_output,
                    suite_preset=suite_preset,
                    resume=resume_dir is not None,
                )
                phase_results.append(
                    {"phase": phase.name, "exit_code": phase_exit, "output": str(phase_output)}
                )
                if phase_exit >= 2:
                    return WorkflowResult(
                        output_dir=resolved_output,
                        exit_code=phase_exit,
                        phase_results=tuple(phase_results),
                        dry_run=False,
                    )
                worst_exit = max(worst_exit, phase_exit)

            if suite_preset.run_smoke_check:
                smoke_check = _run_script(
                    SCRIPTS_DIR / "check_openhands_smoke.py",
                    [str(resolved_output)],
                )
                if smoke_check != 0:
                    return WorkflowResult(
                        output_dir=resolved_output,
                        exit_code=smoke_check,
                        phase_results=tuple(phase_results),
                        dry_run=False,
                    )
                worst_exit = max(worst_exit, smoke_check)

            if suite_preset.merge_pilot:
                sanity_output = resolved_output / "sanity3"
                batch_output = resolved_output / "batch2"
                if (sanity_output / "suite.json").is_file() and (batch_output / "suite.json").is_file():
                    merge_exit = _run_script(
                        SCRIPTS_DIR / "merge_openhands_pilot.py",
                        [str(resolved_output), str(sanity_output), str(batch_output)],
                    )
                    worst_exit = max(worst_exit, merge_exit)

            _run_post_analysis(resolved_output, suite_preset, suite_preset.phases)

    return WorkflowResult(
        output_dir=resolved_output,
        exit_code=worst_exit,
        phase_results=tuple(phase_results),
        dry_run=False,
    )


def _run_phase(
    *,
    local_config: LocalConfig,
    loaded_config: Any,
    phase: SuitePhase,
    output_dir: Path,
    suite_preset: SuitePreset,
    resume: bool,
) -> int:
    task_count_hint = _phase_task_count_hint(phase, suite_preset)
    print(
        f"==> suite={suite_preset.name} phase={phase.name} tasks={task_count_hint} "
        f"output={output_dir}",
        file=sys.stderr,
    )
    retry_rate_limit = (
        phase.retry_rate_limit
        if phase.retry_rate_limit is not None
        else suite_preset.default_retry_rate_limit
    )
    task_ids = list(phase.task_ids) if phase.task_ids else None
    try:
        result = run_agent_on_path(
            phase.task_root if phase.task_root.is_file() else phase.task_root,
            output_dir,
            loaded_config.run_config,
            agent_config_summary=loaded_config.summary,
            num_workers=local_config.run.workers,
            progress=True,
            task_ids=task_ids,
            retry_rate_limit=retry_rate_limit,
            resume_dir=output_dir if resume else None,
            resume_mode=resume,
            extra_agent_passes=local_config.run.extra_agent_passes,
            eval_docker=local_config.run.eval_docker,
            agent_docker=local_config.run.agent_docker,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if result.get("mode") == "suite":
        return 0 if result.get("summary", {}).get("failed") == 0 else 1
    return 0 if result.get("status") == "passed" else 1


def _run_preflight(
    local_config: LocalConfig,
    suite_preset: SuitePreset,
    *,
    output_dir: Path,
    llm_health_check: bool,
) -> int:
    args = [
        sys.executable,
        str(PREFLIGHT_SCRIPT),
        "--bootstrap",
        "--agent",
        local_config.agent.kind,
        "--local-config",
        str(local_config.config_path),
        "--output-dir",
        str(output_dir),
    ]
    if local_config.run.agent_docker or local_config.run.eval_docker:
        args.append("--docker-suite")
    if llm_health_check:
        args.append("--llm-health-check")
    if suite_preset.strict_preflight:
        args.append("--strict")
    completed = subprocess.run(args, check=False)
    return int(completed.returncode)


def _validate_resume(output_dir: Path, *, require_docker_eval: bool) -> None:
    scripts_path = str(SCRIPTS_DIR)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    import validate_suite_resume

    errors = validate_suite_resume.validate_suite_resume(
        output_dir,
        require_docker_eval=require_docker_eval,
    )
    if errors:
        for error in errors:
            print(f"resume validation: {error}", file=sys.stderr)
        raise RuntimeError("resume validation failed")


def _run_post_analysis(
    output_dir: Path,
    suite_preset: SuitePreset,
    phases: tuple[SuitePhase, ...],
) -> None:
    targets = [output_dir]
    if suite_preset.name == "pilot5":
        targets = [output_dir / "sanity3", output_dir / "batch2"]

    for target in targets:
        if not (target / "suite.json").is_file():
            continue
        _run_script(SCRIPTS_DIR / "analyze_featurelift_suite.py", [str(target)])
        _run_script(SCRIPTS_DIR / "analyze_benchmark_suite.py", [str(target)])
        if suite_preset.run_infra_summary:
            _run_script(SCRIPTS_DIR / "summarize_suite_infra.py", [str(target)])
        if suite_preset.run_entanglement_report:
            _run_script(
                SCRIPTS_DIR / "report_entanglement_coverage.py",
                ["--suite-dir", str(target)],
            )


def _run_script(script: Path, args: list[str]) -> int:
    if not script.is_file():
        return 0
    completed = subprocess.run([sys.executable, str(script), *args], check=False)
    return int(completed.returncode)


def _print_dry_run_summary(
    local_config: LocalConfig,
    suite_preset: SuitePreset,
    policy: RuntimePolicy,
    *,
    output_dir: Path | None,
) -> None:
    payload = {
        "config": str(local_config.config_path),
        "suite": suite_preset.name,
        "model": local_config.llm.model,
        "base_url": local_config.llm.base_url,
        "output_dir": str(output_dir) if output_dir else "",
        "phases": [
            {
                "name": phase.name,
                "task_root": str(phase.task_root),
                "task_ids": list(phase.task_ids),
            }
            for phase in suite_preset.phases
        ],
        "run_smoke_check": suite_preset.run_smoke_check,
        "runtime_env": policy.env,
        "agent_docker_network": policy.agent_docker_network,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_setup_summary(
    local_config: LocalConfig,
    suite_preset: SuitePreset,
    policy: RuntimePolicy,
) -> None:
    phase_count = len(suite_preset.phases)
    task_hint = {
        "sanity": "3 tasks",
        "smoke": "1 task (iniconfig smoke)",
        "pilot5": "5 tasks (sanity3 + batch2)",
        "main": "~100 tasks",
        "custom": f"custom under {local_config.run.custom_task_root}",
    }.get(suite_preset.name, "")
    print("setup: ok", file=sys.stderr)
    print(f"  config:   {local_config.config_path}", file=sys.stderr)
    print(f"  model:    {local_config.llm.model}", file=sys.stderr)
    print(f"  base_url: {local_config.llm.base_url}", file=sys.stderr)
    print(f"  suite:    {suite_preset.name} ({task_hint}, {phase_count} phase(s))", file=sys.stderr)
    if policy.agent_docker_network:
        print(f"  network:  FEATURELIFTBENCH_AGENT_DOCKER_NETWORK={policy.agent_docker_network}", file=sys.stderr)
    print(f"  steps:    {local_config.agent.max_steps}", file=sys.stderr)
    print(f"  workers:  {local_config.run.workers}", file=sys.stderr)


def _phase_task_count_hint(phase: SuitePhase, suite_preset: SuitePreset) -> str:
    if phase.task_ids:
        return str(len(phase.task_ids))
    if phase.task_root.is_file():
        return "1"
    if suite_preset.name == "main":
        return "~100"
    if suite_preset.name == "sanity":
        return "3"
    if suite_preset.name == "smoke":
        return "1"
    if suite_preset.name == "pilot5":
        if phase.name == "sanity3":
            return "3"
        if phase.name == "batch2":
            return "2"
    return "?"
