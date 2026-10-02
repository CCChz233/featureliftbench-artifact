"""OpenHands wrapper for FeatureLiftBench agent runs."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .llm_env import apply_openhands_llm_env
from .llm_usage_proxy import maybe_start_openhands_usage_proxy
from .openhands_usage import CONDENSER_MODE_ENV
from .openhands_usage import CUSTOM_CONDENSER_MODES
from .openhands_usage import context_policy_audit_fields
from .openhands_usage import looks_like_openhands_step
from .openhands_usage import openhands_context_policy
from .openhands_usage import openhands_context_limits
from .openhands_usage import parse_openhands_compression_events
from .openhands_usage import resolve_events_path
from .openhands_usage import write_usage_from_events
from .resource_limits import command_output_limit_bytes


USAGE_SCHEMA_VERSION = "featureliftbench.agent_usage.v1"
DEFAULT_OPENHANDS_COMMAND_ENV = "FEATURELIFTBENCH_OPENHANDS_COMMAND"
PROMPT_APPEND_FILE_ENV = "FEATURELIFTBENCH_OPENHANDS_PROMPT_APPEND_FILE"
RAW_USAGE_FILENAMES = ("openhands_usage.json", "usage.json")
OPENHANDS_TOOL_VALIDATION_ERROR_RETURN_CODE = 86
OPENHANDS_INFRASTRUCTURE_ERROR_RETURN_CODE = OPENHANDS_TOOL_VALIDATION_ERROR_RETURN_CODE
CGVL_FINISH_GATE_RETURN_CODE = 87
INFRASTRUCTURE_ERROR_FILE = "openhands_infrastructure_error.json"


@dataclass(frozen=True)
class OpenHandsRunnerConfig:
    workspace_dir: Path
    task_file: Path
    submission_dir: Path
    agent_output_dir: Path
    model: str = ""
    openhands_command: str = ""
    timeout_seconds: int = 3600


@dataclass(frozen=True)
class _RunCommandResult:
    returncode: int
    timed_out: bool = False
    log_limit_exceeded: bool = False
    step_limit_exceeded: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    assistant_steps: int = 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.error(f"unsupported command: {args.command}")
    return run(
        OpenHandsRunnerConfig(
            workspace_dir=args.workspace,
            task_file=args.task_file,
            submission_dir=args.submission_dir,
            agent_output_dir=args.agent_output_dir,
            model=args.model or os.environ.get("FEATURELIFTBENCH_MODEL", ""),
            openhands_command=args.openhands_command
            or os.environ.get(DEFAULT_OPENHANDS_COMMAND_ENV, ""),
            timeout_seconds=args.timeout_seconds,
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="featureliftbench.openhands_runner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run OpenHands on a FeatureLiftBench task")
    run_parser.add_argument("--workspace", type=Path, required=True)
    run_parser.add_argument("--task-file", type=Path, required=True)
    run_parser.add_argument("--submission-dir", type=Path, required=True)
    run_parser.add_argument("--agent-output-dir", type=Path, required=True)
    run_parser.add_argument("--model", default="")
    run_parser.add_argument(
        "--openhands-command",
        default="",
        help=(
            "OpenHands headless command template. Placeholders: {workspace}, "
            "{task_file}, {submission_dir}, {agent_output_dir}, {prompt_file}, {model}, {python}"
        ),
    )
    run_parser.add_argument("--timeout-seconds", type=int, default=3600)
    return parser


def run(config: OpenHandsRunnerConfig) -> int:
    config.agent_output_dir.mkdir(parents=True, exist_ok=True)
    # TD-Cognition legacy lock files must not block mkdir; two-phase uses a real dir.
    if config.submission_dir.exists() and not config.submission_dir.is_dir():
        config.submission_dir.unlink()
    config.submission_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = config.agent_output_dir / "openhands_task.md"
    prompt_file.write_text(_build_openhands_prompt(config), encoding="utf-8")

    command_template = config.openhands_command.strip()
    if not command_template:
        _write_command_record(
            config,
            prompt_file=prompt_file,
            command_template="",
            command=[],
            configured=False,
            error=f"{DEFAULT_OPENHANDS_COMMAND_ENV} or --openhands-command is required",
        )
        _write_usage(
            config,
            exit_status="not_configured",
            returncode=2,
            duration_seconds=0.0,
            raw_usage=None,
        )
        print(
            f"OpenHands command is not configured. Set {DEFAULT_OPENHANDS_COMMAND_ENV} "
            "or pass --agent-command.",
            file=sys.stderr,
        )
        return 2

    try:
        command = _render_openhands_command(config, prompt_file, command_template)
    except ValueError as exc:
        _write_command_record(
            config,
            prompt_file=prompt_file,
            command_template=command_template,
            command=[],
            configured=False,
            error=str(exc),
        )
        _write_usage(
            config,
            exit_status="invalid_command_template",
            returncode=2,
            duration_seconds=0.0,
            raw_usage=None,
        )
        print(str(exc), file=sys.stderr)
        return 2

    _write_command_record(
        config,
        prompt_file=prompt_file,
        command_template=command_template,
        command=command,
        configured=True,
        error="",
    )
    stdout_log = config.agent_output_dir / "openhands_stdout.log"
    stderr_log = config.agent_output_dir / "openhands_stderr.log"
    events_log = config.agent_output_dir / "openhands_events.jsonl"
    env = os.environ.copy()
    env.update(
        {
            "FEATURELIFTBENCH_WORKSPACE": str(config.workspace_dir),
            "FEATURELIFTBENCH_TASK_FILE": str(config.task_file),
            "FEATURELIFTBENCH_SUBMISSION_DIR": str(config.submission_dir),
            "FEATURELIFTBENCH_AGENT_OUTPUT_DIR": str(config.agent_output_dir),
            "FEATURELIFTBENCH_OPENHANDS_PROMPT_FILE": str(prompt_file),
            "FEATURELIFTBENCH_MODEL": config.model,
        }
    )
    env = apply_openhands_llm_env(env)
    env.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
    _ensure_harness_pythonpath(env)
    try:
        _maybe_seed_agent_settings(command, env, config.agent_output_dir)
        command = _wrap_custom_condenser_command(command, env)
        _write_command_record(
            config,
            prompt_file=prompt_file,
            command_template=command_template,
            command=command,
            configured=True,
            error="",
        )
    except (RuntimeError, ValueError) as exc:
        try:
            _write_context_policy(
                config,
                env,
                status="configuration_failed",
                error=str(exc),
            )
        except ValueError:
            _write_invalid_context_policy(config, env, str(exc))
        _write_usage(
            config,
            exit_status="context_configuration_failed",
            returncode=2,
            duration_seconds=0.0,
            raw_usage=None,
        )
        print(f"FeatureLiftBench: {exc}", file=sys.stderr)
        return 2

    start = time.monotonic()
    proxy = maybe_start_openhands_usage_proxy(env, config.agent_output_dir)
    try:
        if proxy is not None:
            proxy.start()
            _point_openhands_to_proxy(env, proxy.base_url)
        command_result = _run_command(
            command,
            cwd=config.workspace_dir,
            env=env,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            events_log=events_log,
            timeout_seconds=config.timeout_seconds,
        )
    finally:
        if proxy is not None:
            proxy.close()
    duration_seconds = time.monotonic() - start
    returncode = command_result.returncode
    events_path = resolve_events_path(
        config.agent_output_dir,
        stdout_log=stdout_log,
    )
    infrastructure_error = _detect_openhands_infrastructure_error(events_path)
    if infrastructure_error is not None:
        recovered = returncode == 0 and _submission_has_python_files(
            config.submission_dir
        )
        infrastructure_error["promoted_to_process_failure"] = not recovered
        (config.agent_output_dir / INFRASTRUCTURE_ERROR_FILE).write_text(
            json.dumps(infrastructure_error, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # OpenHands may emit one security_risk validation error, recover, and
        # still exit 0 with a real submission. Do not rewrite that as process
        # failure; keep the audit file. Empty submissions stay failed.
        if returncode == 0 and not recovered:
            returncode = OPENHANDS_INFRASTRUCTURE_ERROR_RETURN_CODE
    raw_usage_path = config.agent_output_dir / "openhands_usage.json"
    if events_path is not None and not raw_usage_path.is_file():
        write_usage_from_events(
            events_path,
            raw_usage_path,
        )
    raw_usage = _read_raw_usage(config.agent_output_dir)
    raw_usage = _merge_compression_audit(
        raw_usage,
        parse_openhands_compression_events(events_path),
    )
    if returncode == 0:
        returncode = _maybe_enforce_cgvl_finish_gate(config, env)
    _maybe_write_pre_submit_audit(config, env, events_path)
    exit_status = "passed" if returncode == 0 else "openhands_failed"
    if command_result.log_limit_exceeded:
        exit_status = "log_limit_exceeded"
    elif command_result.step_limit_exceeded:
        exit_status = "step_limit_exceeded"
    elif returncode == 124:
        exit_status = "timeout"
    elif returncode == 127:
        exit_status = "command_not_found"
    elif returncode == OPENHANDS_INFRASTRUCTURE_ERROR_RETURN_CODE:
        exit_status = str(
            (infrastructure_error or {}).get("failure_class") or "tool_validation_error"
        )
    elif returncode == CGVL_FINISH_GATE_RETURN_CODE:
        exit_status = "cgvl_gate_failed"
    _write_usage(
        config,
        exit_status=exit_status,
        returncode=returncode,
        duration_seconds=duration_seconds,
        raw_usage=raw_usage,
        assistant_steps=command_result.assistant_steps,
        infrastructure_error=infrastructure_error,
    )
    print(f"OpenHands wrapper finished with return code {returncode}.")
    return returncode


def _point_openhands_to_proxy(env: dict[str, str], proxy_base_url: str) -> None:
    for key in (
        "LLM_BASE_URL",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "FEATURELIFTBENCH_API_BASE",
        "DEEPSEEK_API_BASE",
        "LITELLM_API_BASE",
    ):
        env[key] = proxy_base_url
    for key in (
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "FEATURELIFTBENCH_API_KEY",
        "DEEPSEEK_API_KEY",
        "LITELLM_API_KEY",
    ):
        if key in env:
            env[key] = "featureliftbench-proxy"


_TRUTHY = {"true", "1", "yes", "on"}

_AGENT_SETTINGS_GENERATOR = """
from featureliftbench.openhands_condenser.seed import seed_agent_settings
seed_agent_settings()
"""


def _maybe_seed_agent_settings(
    command: list[str],
    env: dict[str, str],
    agent_output_dir: Path,
) -> None:
    """Create an isolated persistence directory and any required agent settings.

    Token mode and custom condensers always generate a strict settings file.
    Legacy mode only creates one for the existing native-tool-calling override.
    """
    policy = openhands_context_policy(env)
    native = env.get("LLM_NATIVE_TOOL_CALLING")
    needs_native_override = native is not None and native.strip().lower() not in _TRUTHY

    persist_dir = agent_output_dir / "openhands_persistence"
    persist_dir.mkdir(parents=True, exist_ok=True)
    env["OPENHANDS_PERSISTENCE_DIR"] = str(persist_dir)
    settings_path = persist_dir / "agent_settings.json"
    metadata_path = agent_output_dir / "agent_settings_metadata.json"

    _write_context_policy(
        config=None,
        env=env,
        agent_output_dir=agent_output_dir,
        status="configured",
    )
    if not policy.requires_seeded_settings and not needs_native_override:
        return

    interpreter = _resolve_openhands_python(command)
    if interpreter is None:
        message = "could not resolve the OpenHands interpreter for agent settings"
        if policy.requires_seeded_settings:
            raise RuntimeError(message)
        print(f"FeatureLiftBench: {message}; override skipped.", file=sys.stderr)
        return

    gen_env = dict(env)
    _ensure_harness_pythonpath(gen_env)
    gen_env["FLB_AGENT_SETTINGS_OUT"] = str(settings_path)
    gen_env["FLB_AGENT_SETTINGS_META_OUT"] = str(metadata_path)
    try:
        result = subprocess.run(
            [interpreter, "-c", _AGENT_SETTINGS_GENERATOR],
            env=gen_env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if policy.requires_seeded_settings:
            raise RuntimeError(f"OpenHands agent settings generation failed: {exc}") from exc
        print(f"FeatureLiftBench: OpenHands settings override skipped: {exc}", file=sys.stderr)
        return
    log_path = agent_output_dir / "agent_settings_seed.log"
    log_path.write_text(
        f"returncode={result.returncode}\n"
        f"settings_path={settings_path}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n",
        encoding="utf-8",
    )
    succeeded = result.returncode == 0 and settings_path.is_file()
    if policy.requires_seeded_settings:
        succeeded = succeeded and metadata_path.is_file()
    if not succeeded:
        message = "failed to generate isolated OpenHands agent settings"
        if policy.requires_seeded_settings:
            raise RuntimeError(f"{message} (see agent_settings_seed.log)")
        print(f"FeatureLiftBench: {message} (see agent_settings_seed.log).", file=sys.stderr)
        return

    metadata: dict[str, Any] = {}
    if metadata_path.is_file():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metadata = loaded
        except (OSError, json.JSONDecodeError):
            metadata = {}
        metadata_path.unlink(missing_ok=True)
    _write_context_policy(
        config=None,
        env=env,
        agent_output_dir=agent_output_dir,
        status="configured",
        runtime_metadata=metadata,
    )


def _resolve_openhands_python(command: list[str]) -> str | None:
    """Best-effort resolution of the Python interpreter that runs OpenHands."""
    if not command:
        return None
    binary = shutil.which(command[0]) or command[0]
    try:
        with open(binary, encoding="utf-8", errors="replace") as handle:
            first_line = handle.readline().strip()
    except OSError:
        first_line = ""
    if first_line.startswith("#!"):
        shebang = first_line[2:].strip()
        interpreter = shebang.split()[0] if shebang else ""
        if interpreter and os.path.exists(interpreter):
            return interpreter
    fallback = "/opt/uv-tools/openhands/bin/python"
    if os.path.exists(fallback):
        return fallback
    return None


def _write_context_policy(
    config: OpenHandsRunnerConfig | None,
    env: dict[str, str],
    agent_output_dir: Path | None = None,
    *,
    status: str = "pending",
    error: str = "",
    runtime_metadata: dict[str, Any] | None = None,
) -> None:
    output_dir = agent_output_dir or (config.agent_output_dir if config is not None else None)
    if output_dir is None:
        raise ValueError("agent_output_dir is required for context policy")
    policy = openhands_context_policy(env)
    payload: dict[str, Any] = {
        "schema_version": "featureliftbench.openhands_context_policy.v1",
        "runtime": "openhands",
        "profile": env.get("FEATURELIFTBENCH_AGENT_PROFILE", ""),
        "model": (config.model if config is not None else env.get("FEATURELIFTBENCH_MODEL", "")),
        "status": status,
        "compression_mode": policy.compression_mode,
        "condenser_kind": _condenser_kind_for_mode(policy.compression_mode),
        "attention_window": policy.condenser_attention_window,
        "context_window_tokens": policy.context_window_tokens,
        "reserved_output_tokens": policy.reserved_output_tokens,
        "trigger_tokens": policy.condenser_trigger_tokens,
        "estimated_target_tokens": policy.condenser_target_tokens,
        "keep_first": policy.condenser_keep_first,
        "event_fallback": policy.condenser_max_events,
        "persistence_dir": str(output_dir / "openhands_persistence"),
        "settings_path": str(output_dir / "openhands_persistence" / "agent_settings.json"),
        "error": error,
    }
    if runtime_metadata:
        for key in ("openhands_version", "openhands_sdk_version", "settings"):
            value = runtime_metadata.get(key)
            if value is not None:
                payload[key] = value
    (output_dir / "context_policy.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_invalid_context_policy(
    config: OpenHandsRunnerConfig,
    env: dict[str, str],
    error: str,
) -> None:
    payload = {
        "schema_version": "featureliftbench.openhands_context_policy.v1",
        "runtime": "openhands",
        "profile": env.get("FEATURELIFTBENCH_AGENT_PROFILE", ""),
        "model": config.model,
        "status": "configuration_failed",
        "compression_mode": env.get(CONDENSER_MODE_ENV, ""),
        "error": error,
    }
    (config.agent_output_dir / "context_policy.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _build_openhands_prompt(config: OpenHandsRunnerConfig) -> str:
    from .ablation import ablation_options_from_env

    task_text = config.task_file.read_text(encoding="utf-8")
    options = ablation_options_from_env(os.environ)
    if options.contract_closure_gate_lite_rescue_plus:
        from .contract_closure_gate.common import CONTRACT_CLOSURE_PHASE_ENV

        closure_phase = (
            str(os.environ.get(CONTRACT_CLOSURE_PHASE_ENV, "primary")).strip().lower()
            or "primary"
        )
        if closure_phase == "repair":
            # The repair task is already a complete, public-only, edit-first prompt.
            # Wrapping it in the normal implementation prompt caused bounded repairs
            # to restart repository discovery and exhaust their step budget.
            return task_text
    if options.mount_public_tests:
        public_line = (
            "- Public tests are under `public_tests/` and may be run for feedback.\n"
        )
        test_hint = (
            "When you need to run tests, prefer:\n\n"
            "```bash\n"
            "PYTHONPATH=submission pytest public_tests/\n"
            "```\n\n"
        )
        complete_note = (
            "- Keep the implementation behavior-complete, not only tailored to public tests.\n\n"
        )
        source_line = "- Source code to inspect is under `repo/`.\n"
    elif options.source_context == "contract_only":
        from .source_ablation import openhands_contract_only_wrapper_lines

        source_line, public_line, test_hint = openhands_contract_only_wrapper_lines()
        complete_note = (
            "- Keep the implementation behavior-complete against the Required Output API and "
            "included behaviors.\n\n"
        )
    else:
        public_line = (
            "- Benchmark-authored evaluator tests are **not mounted**. Upstream tests, docs, "
            "and examples already present under `repo/` remain available.\n"
        )
        test_hint = (
            "Implement from the public contract and `repo/`. Discover relevant upstream tests "
            "when present, adapt or write your own tests, and run them before submitting. "
            "The evaluator runs its private test tiers only after submit.\n\n"
        )
        complete_note = (
            "- Keep the implementation behavior-complete against the Required Output API and "
            "included behaviors.\n\n"
        )
        source_line = "- Source code to inspect is under `repo/`.\n"
    td_section = ""
    sc_section = ""
    tfl_section = ""
    closure_section = ""
    submission_line = f"- Final output must be written under `{config.submission_dir}`.\n"
    required_finish = (
        "## Required Finish State\n\n"
        "Create a normal Python submission layout:\n\n"
        "```text\n"
        "submission/\n"
        "  featurelifted/\n"
        "    __init__.py\n"
        "    ...\n"
        "```\n\n"
    )
    if options.self_contract:
        from .self_contract.common import SELF_CONTRACT_PHASE_ENV
        from .self_contract import openhands_author_appendix
        from .self_contract import openhands_implement_appendix

        phase = (
            str(os.environ.get(SELF_CONTRACT_PHASE_ENV, "implement")).strip().lower()
            or "implement"
        )
        if phase in {"author", "author_repair"}:
            sc_section = (
                "## Self-Authored Contract Phase A\n\n"
                + openhands_author_appendix()
                + "\n"
            )
            submission_line = (
                "- `submission/` may exist but must remain **empty** in this phase. "
                "Do not create `submission/featurelifted/`.\n"
            )
            required_finish = (
                "## Required Finish State\n\n"
                "Deliver authored contracts only:\n\n"
                "```text\n"
                "contracts/\n"
                "  test_*.py\n"
                "  README.md\n"
                "```\n\n"
                "Then finish. Implementation happens in a later phase.\n\n"
            )
            test_hint = (
                "Write pytest modules under `contracts/` that import `featurelifted` "
                "and assert TASK behaviors. Use `repo/` and `RUNTIME_FACTS.md` as hints. "
                "Do not implement the full submission yet.\n\n"
            )
        else:
            sc_section = (
                "## Self-Authored Contract Phase B\n\n"
                + openhands_implement_appendix()
                + "\n"
            )
            test_hint = (
                "Run your frozen contracts before submit:\n\n"
                "```bash\n"
                "PYTHONPATH=submission pytest contracts/ -q\n"
                "```\n\n"
            )
    elif options.td_cognition:
        from .td_cognition import TD_PHASE_ENV
        from .td_cognition import openhands_phase1_appendix
        from .td_cognition import openhands_phase2_appendix

        phase = str(os.environ.get(TD_PHASE_ENV, "implement")).strip().lower() or "implement"
        if phase == "cognition":
            td_section = (
                "## TD-Cognition Phase 1\n\n"
                + openhands_phase1_appendix()
                + "\n"
            )
            submission_line = (
                "- `submission/` may exist but must remain **empty** in this phase. "
                "Do not create `submission/featurelifted/`.\n"
            )
            required_finish = (
                "## Required Finish State\n\n"
                "Deliver cognition artifacts only:\n\n"
                "```text\n"
                "COGNITION.md\n"
                "probes/\n"
                "  test_*.py\n"
                "```\n\n"
                "Then finish. Implementation happens in a later phase.\n\n"
            )
            test_hint = (
                "Write and run your own probes under `probes/` against `repo/` or "
                "standalone checks. Do not import `submission.featurelifted`.\n\n"
            )
        else:
            td_section = (
                "## TD-Cognition Phase 2\n\n"
                + openhands_phase2_appendix(workspace_dir=config.workspace_dir)
                + "\n"
            )
    elif options.test_first_lift:
        from .test_first_lift import openhands_appendix

        tfl_section = openhands_appendix() + "\n"
        test_hint = (
            "Use `./flb-test-first freeze` after writing characterization cases, "
            "then implement `submission/featurelifted/`, then "
            "`./flb-test-first verify`.\n\n"
        )
        required_finish = (
            "## Required Finish State\n\n"
            "Leave both frozen characterization evidence and a working submission:\n\n"
            "```text\n"
            "characterization/\n"
            "oracle.json\n"
            "characterization.lock\n"
            "submission/\n"
            "  featurelifted/\n"
            "    __init__.py\n"
            "    ...\n"
            "```\n\n"
        )
    elif options.contract_closure_budget_control:
        from .contract_closure_budget_control import openhands_appendix

        closure_section = (
            "## Equal-Budget Implementation Review\n\n"
            + openhands_appendix()
            + "\n"
        )
        test_hint = (
            "Use ordinary local checks that you judge useful, then perform one final "
            "review against the public Required Output API.\n\n"
        )
    elif options.pre_submit_contract_audit:
        from .pre_submit_contract_audit import openhands_appendix

        closure_section = (
            "## Pre-submit Explicit-Contract Audit\n\n"
            + openhands_appendix()
            + "\n"
        )
        test_hint = (
            "Before finishing, walk the public Required API and Bxxx clauses already "
            "in TASK.md against `submission/`. Do not invent new contracts or hunt "
            "for evaluator tests.\n\n"
        )
    elif options.spec_adversarial_self_test:
        from .spec_adversarial import openhands_appendix as sa_openhands_appendix

        closure_section = (
            "## Spec-grounded adversarial self-test\n\n"
            + sa_openhands_appendix()
            + "\n"
        )
        test_hint = (
            "Fill contract_cases/ stubs from contract_matrix.json and run "
            "./run_contract_check.py until ok=true. Do not finish while red. "
            "Do not hunt public_tests/ or hidden_tests/.\n\n"
        )
    elif options.obligation_guided:
        from .obligation_guided import openhands_appendix as og_openhands_appendix

        closure_section = (
            "## Obligation-Guided Feature Lifting\n\n"
            + og_openhands_appendix()
            + "\n"
        )
        test_hint = (
            "Fill obligation_ledger.json so every public-contract row cites "
            "repo_evidence.path and implementation.path. Do not add rows, "
            "guess Hidden tests, or treat pytest as coverage.\n\n"
        )
    elif options.cgvl:
        from .cgvl import openhands_appendix as cgvl_openhands_appendix

        closure_section = (
            "## Contract-Guided Verification Loop\n\n"
            + cgvl_openhands_appendix()
            + "\n"
        )
        test_hint = (
            "Fill cgvl_cells/ from cgvl_matrix.json and run ./run_cgvl_check.py "
            "until ok=true. Do not finish while red. Do not hunt public_tests/ "
            "or hidden_tests/.\n\n"
        )
    elif options.adaptive_budget_v2:
        from .adaptive_budget_v2 import ADAPTIVE_BUDGET_V2_PHASE_ENV
        from .adaptive_budget_v2 import targeted_repair_openhands_appendix

        phase = (
            str(os.environ.get(ADAPTIVE_BUDGET_V2_PHASE_ENV, "primary")).strip().lower()
            or "primary"
        )
        if phase == "repair":
            closure_section = (
                "## Targeted Repair Mode\n\n"
                + targeted_repair_openhands_appendix()
                + "\n"
            )
            test_hint = (
                "Run agent-authored local checks after each change "
                "(for example `python -c \"from featurelifted import ...\"`). "
                "Do not hunt for benchmark evaluator tests.\n\n"
            )
    elif (
        options.contract_closure_gate
        or options.contract_closure_gate_lite
        or options.contract_closure_gate_lite_v1
        or options.contract_closure_gate_lite_rescue
        or options.contract_closure_gate_lite_rescue_plus
        or options.contract_closure_gate_v3
    ):
        from .contract_closure_gate import openhands_appendix

        closure_section = (
            "## Public Contract Closure Gate\n\n"
            + openhands_appendix(
                lite=options.contract_closure_gate_lite
                or options.contract_closure_gate_lite_v1
                or options.contract_closure_gate_lite_rescue
                or options.contract_closure_gate_lite_rescue_plus
                or options.contract_closure_gate_v3,
                frozen_v1=options.contract_closure_gate_lite_v1,
                rescue=options.contract_closure_gate_lite_rescue,
                rescue_plus=options.contract_closure_gate_lite_rescue_plus,
                v3=options.contract_closure_gate_v3,
            )
            + "\n"
        )
        if options.contract_closure_gate_lite_rescue_plus:
            test_hint = (
                "After implementing, write one composed behavior case (a second only "
                "when necessary) and run `./flb-contract-check --lite-plus --summary`. "
                "Do not chase complete behavior coverage.\n\n"
            )
            required_finish = (
                "## Required Finish State\n\n"
                "Leave a working submission and one or two concise public behavior "
                "smoke cases under `contract_cases/`.\n\n"
            )
        elif options.contract_closure_gate_v3:
            test_hint = (
                "After implementing, write exactly two focused cases and run "
                "`./flb-contract-check --micro --summary`. Do not chase complete "
                "behavior coverage.\n\n"
            )
            required_finish = (
                "## Required Finish State\n\n"
                "Leave a working submission and two concise public behavior smoke "
                "cases under `contract_cases/`.\n\n"
            )
        elif (
            options.contract_closure_gate_lite_v1
            or options.contract_closure_gate_lite_rescue
        ):
            from .contract_closure_gate.workspace import _lite_v1_silent_finish

            silent_finish = (
                options.contract_closure_gate_lite_v1 and _lite_v1_silent_finish()
            )
            test_hint = (
                "Run `./flb-contract-check --structure-only --summary` after "
                "implementing."
                + (
                    ""
                    if silent_finish
                    else " Do not spend steps authoring behavior cases."
                )
                + "\n\n"
            )
            if not silent_finish:
                required_finish = (
                    "## Required Finish State\n\n"
                    "Leave a structurally closed working submission under "
                    "`submission/featurelifted/`.\n\n"
                )
        elif options.contract_closure_gate_lite:
            test_hint = (
                "Run `./flb-contract-check --structure-only --summary` after "
                "implementing. Do not spend steps authoring behavior cases.\n\n"
            )
            required_finish = (
                "## Required Finish State\n\n"
                "Leave a structurally closed working submission under "
                "`submission/featurelifted/`.\n\n"
            )
        else:
            test_hint = (
                "Run `./flb-contract-check` after implementing and adding behavior cases. "
                "Resolve every actionable public-contract finding before submitting.\n\n"
            )
            required_finish = (
                "## Required Finish State\n\n"
                "Leave public behavior evidence and a working submission:\n\n"
                "```text\n"
                "contract_cases/\n"
                "  *.py\n"
                "submission/\n"
                "  featurelifted/\n"
                "    __init__.py\n"
                "    ...\n"
                "```\n\n"
            )
    prompt = (
        "# FeatureLiftBench Task for OpenHands\n\n"
        "You are being evaluated as the coding agent for FeatureLiftBench.\n\n"
        "## Workspace Contract\n\n"
        f"- Workspace root: `{config.workspace_dir}`\n"
        f"{source_line}"
        f"{public_line}"
        "- All benchmark-authored evaluator tests and evaluation files are private boundaries; "
        "do not use them as inputs.\n"
        f"{submission_line}"
        "- The importable package must be `submission/featurelifted/` "
        "(phase-2 / normal runs only).\n"
        "- Do not place the answer in a top-level `featurelifted/` directory.\n"
        "- Prefer not to create `pyproject.toml`; the evaluator imports `submission/featurelifted` "
        "directly via `PYTHONPATH`.\n"
        "- If a `pyproject.toml` is truly necessary, use only `setuptools.build_meta` as the "
        "build backend; never use `setuptools.backends._legacy:_Backend`.\n"
        f"{complete_note}"
        f"{td_section}"
        f"{sc_section}"
        f"{tfl_section}"
        f"{closure_section}"
        f"{required_finish}"
        f"{test_hint}"
        "## Task\n\n"
        f"{task_text}\n"
    )
    append_path_text = os.environ.get(PROMPT_APPEND_FILE_ENV, "").strip()
    if not append_path_text:
        return prompt
    append_path = Path(append_path_text)
    if not append_path.is_file():
        raise FileNotFoundError(
            f"{PROMPT_APPEND_FILE_ENV} does not point to a file: {append_path}"
        )
    appendix = append_path.read_text(encoding="utf-8")
    return (
        prompt
        + "\n## Registered Experimental Condition\n\n"
        + "The following condition text is recorded by the experiment runner. "
        + "It does not grant access to hidden tests or evaluation files.\n\n"
        + appendix.rstrip()
        + "\n"
    )


def _render_openhands_command(
    config: OpenHandsRunnerConfig,
    prompt_file: Path,
    command_template: str,
) -> list[str]:
    values = {
        "workspace": str(config.workspace_dir),
        "task_file": str(config.task_file),
        "submission_dir": str(config.submission_dir),
        "agent_output_dir": str(config.agent_output_dir),
        "prompt_file": str(prompt_file),
        "model": config.model,
        "python": sys.executable,
    }
    try:
        rendered = command_template.format(**values)
    except KeyError as exc:
        raise ValueError(f"unknown OpenHands command placeholder: {exc.args[0]}") from exc
    command = shlex.split(rendered)
    if not command:
        raise ValueError("OpenHands command template rendered to an empty command")
    return command


def _wrap_custom_condenser_command(
    command: list[str],
    env: dict[str, str],
) -> list[str]:
    policy = openhands_context_policy(env)
    if policy.compression_mode not in CUSTOM_CONDENSER_MODES:
        return command
    if len(command) >= 3 and command[1:3] == [
        "-m",
        "featureliftbench.openhands_condenser.launch",
    ]:
        return command
    interpreter = _resolve_openhands_python(command)
    if interpreter is None:
        raise RuntimeError(
            "could not resolve the OpenHands interpreter for a custom condenser"
        )
    return [
        interpreter,
        "-m",
        "featureliftbench.openhands_condenser.launch",
        *command[1:],
    ]


def _ensure_harness_pythonpath(env: dict[str, str]) -> None:
    harness_root = str(Path(__file__).resolve().parent.parent)
    existing = [part for part in env.get("PYTHONPATH", "").split(os.pathsep) if part]
    if harness_root not in existing:
        env["PYTHONPATH"] = os.pathsep.join([harness_root, *existing])


def _condenser_kind_for_mode(mode: str) -> str:
    mapping = {
        "token": "LLMSummarizingCondenser",
        "recency_masking": "RecencyMaskingCondenser",
        "artifact_aware": "ArtifactAwareCondenser",
        "verification_aware": "VerificationAwareCondenser",
        "default": "LLMSummarizingCondenser",
    }
    return mapping.get(mode, mode)


def _maybe_enforce_cgvl_finish_gate(
    config: OpenHandsRunnerConfig,
    env: dict[str, str],
) -> int:
    """Reject a nominal OpenHands finish when the CGVL checker is still red."""

    from .ablation import ablation_options_from_env

    options = ablation_options_from_env(env)
    if not options.cgvl:
        return 0
    checker = config.workspace_dir / "run_cgvl_check.py"
    record_path = config.agent_output_dir / "cgvl_finish_gate.json"
    payload: dict[str, Any] = {
        "enforced": True,
        "checker": str(checker),
        "ok": False,
        "returncode": None,
        "error": "",
    }
    if not checker.is_file():
        payload["error"] = "missing run_cgvl_check.py"
        record_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return CGVL_FINISH_GATE_RETURN_CODE
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(checker),
                "--workspace",
                str(config.workspace_dir),
            ],
            cwd=config.workspace_dir,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        payload["returncode"] = completed.returncode
        payload["stdout"] = completed.stdout[-20000:]
        payload["stderr"] = completed.stderr[-20000:]
        evidence_path = config.workspace_dir / "cgvl_evidence.json"
        evidence: dict[str, Any] = {}
        if evidence_path.is_file():
            loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                evidence = loaded
        payload["ok"] = completed.returncode == 0 and bool(evidence.get("ok"))
        payload["red_count"] = evidence.get("red_count")
        payload["green_count"] = evidence.get("green_count")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    record_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if payload["ok"] else CGVL_FINISH_GATE_RETURN_CODE


def _maybe_write_pre_submit_audit(
    config: OpenHandsRunnerConfig,
    env: dict[str, str],
    events_path: Path | None,
) -> None:
    from .ablation import ablation_options_from_env

    options = ablation_options_from_env(env)
    if options.pre_submit_contract_audit:
        from .pre_submit_contract_audit import write_pre_submit_audit

        source = events_path or (config.agent_output_dir / "openhands_events.jsonl")
        write_pre_submit_audit(
            source,
            config.agent_output_dir / "pre_submit_audit.json",
        )
        return
    if options.spec_adversarial_self_test:
        from .spec_adversarial import write_audit

        write_audit(
            config.workspace_dir,
            config.agent_output_dir / "spec_adversarial_audit.json",
        )
        return
    if options.obligation_guided:
        from .obligation_guided import write_audit as write_obligation_audit

        write_obligation_audit(
            config.workspace_dir,
            config.agent_output_dir / "obligation_guided_audit.json",
        )
        return
    if options.cgvl:
        from .cgvl import write_audit as write_cgvl_audit

        write_cgvl_audit(
            config.workspace_dir,
            config.agent_output_dir / "cgvl_audit.json",
        )


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_log: Path,
    stderr_log: Path,
    events_log: Path,
    timeout_seconds: int,
) -> _RunCommandResult:
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    events_log.parent.mkdir(parents=True, exist_ok=True)
    limiter = _OutputLimiter(command_output_limit_bytes(env))
    stdout_capture = _OpenHandsStdoutCapture(
        stdout_log,
        events_log,
        limiter,
        max_steps=_openhands_max_steps(env),
    )
    stderr_capture = _StreamLogCapture(stderr_log, limiter)
    process: subprocess.Popen[bytes] | None = None
    log_limit_event = threading.Event()
    step_limit_event = threading.Event()
    try:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            stderr_capture.write_text(str(exc))
            return _RunCommandResult(returncode=127)
        except PermissionError as exc:
            stderr_capture.write_text(str(exc))
            return _RunCommandResult(returncode=126)

        def pump_stdout() -> None:
            assert process is not None and process.stdout is not None
            try:
                _pump_stream(
                    process=process,
                    stream=process.stdout,
                    capture=stdout_capture,
                    log_limit_event=log_limit_event,
                    step_limit_event=step_limit_event,
                )
            finally:
                stdout_capture.flush()

        def pump_stderr() -> None:
            assert process is not None and process.stderr is not None
            _pump_stream(
                process=process,
                stream=process.stderr,
                capture=stderr_capture,
                log_limit_event=log_limit_event,
                step_limit_event=step_limit_event,
            )

        threads = [
            threading.Thread(target=pump_stdout, daemon=True),
            threading.Thread(target=pump_stderr, daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        deadline = time.monotonic() + max(1, timeout_seconds)
        while process.poll() is None:
            if log_limit_event.is_set():
                _kill_process_group(process)
                break
            if step_limit_event.is_set():
                _kill_process_group(process)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                _kill_process_group(process)
                break
            time.sleep(0.05)

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)

        for thread in threads:
            thread.join(timeout=2)

        if log_limit_event.is_set():
            stderr_capture.write_text(
                "\nFeatureLiftBench: OpenHands output exceeded "
                f"{limiter.limit_bytes} bytes; process group was terminated.\n"
            )
            return _RunCommandResult(
                returncode=125,
                log_limit_exceeded=True,
                stdout_truncated=stdout_capture.truncated,
                stderr_truncated=stderr_capture.truncated,
                assistant_steps=stdout_capture.assistant_steps,
            )
        if step_limit_event.is_set():
            stderr_capture.write_text(
                "\nFeatureLiftBench: OpenHands step limit exceeded "
                f"after {stdout_capture.assistant_steps} step(s); process group was terminated.\n"
            )
            return _RunCommandResult(
                returncode=123,
                step_limit_exceeded=True,
                stdout_truncated=stdout_capture.truncated,
                stderr_truncated=stderr_capture.truncated,
                assistant_steps=stdout_capture.assistant_steps,
            )
        if timed_out:
            return _RunCommandResult(
                returncode=124,
                timed_out=True,
                assistant_steps=stdout_capture.assistant_steps,
            )
        return _RunCommandResult(
            returncode=int(process.returncode or 0),
            assistant_steps=stdout_capture.assistant_steps,
        )
    finally:
        stdout_capture.close()
        stderr_capture.close()


def _pump_stream(
    *,
    process: subprocess.Popen[bytes],
    stream: Any,
    capture: "_StreamCapture",
    log_limit_event: threading.Event,
    step_limit_event: threading.Event,
) -> None:
    try:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            exceeded = capture.append(chunk)
            if (
                isinstance(capture, _OpenHandsStdoutCapture)
                and capture.step_limit_exceeded
                and not step_limit_event.is_set()
            ):
                step_limit_event.set()
                _kill_process_group(process)
                return
            if exceeded and not log_limit_event.is_set():
                log_limit_event.set()
                _kill_process_group(process)
                return
    finally:
        stream.close()


class _OutputLimiter:
    def __init__(self, limit_bytes: int | None) -> None:
        self.limit_bytes = limit_bytes if limit_bytes is None or limit_bytes > 0 else None
        self._seen = 0
        self._lock = threading.Lock()

    def retain(self, chunk: bytes) -> tuple[bytes, bool]:
        if self.limit_bytes is None:
            return chunk, False
        with self._lock:
            remaining = max(0, self.limit_bytes - min(self._seen, self.limit_bytes))
            retained = chunk[:remaining]
            self._seen += len(chunk)
            return retained, len(chunk) > remaining


class _StreamCapture:
    truncated: bool

    def append(self, chunk: bytes) -> bool:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class _StreamLogCapture(_StreamCapture):
    def __init__(self, log_path: Path, limiter: _OutputLimiter) -> None:
        self._limiter = limiter
        self._handle = log_path.open("w", encoding="utf-8")
        self.truncated = False

    def append(self, chunk: bytes) -> bool:
        retained, exceeded = self._limiter.retain(chunk)
        if retained:
            self.write_text(retained.decode("utf-8", errors="replace"))
        if exceeded:
            self.truncated = True
        return exceeded

    def write_text(self, text: str) -> None:
        self._handle.write(text)
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


class _OpenHandsStdoutCapture(_StreamCapture):
    def __init__(
        self,
        stdout_log: Path,
        events_log: Path,
        limiter: _OutputLimiter,
        max_steps: int | None = None,
    ) -> None:
        self._limiter = limiter
        self._max_steps = max_steps
        self._stdout_handle = stdout_log.open("w", encoding="utf-8")
        self._events_handle = events_log.open("w", encoding="utf-8")
        self._buffer = bytearray()
        self.truncated = False
        self.assistant_steps = 0
        self.step_limit_exceeded = False

    def append(self, chunk: bytes) -> bool:
        retained, exceeded = self._limiter.retain(chunk)
        if retained:
            self._buffer.extend(retained)
            self._drain_lines()
        if exceeded:
            self.truncated = True
        return exceeded

    def flush(self) -> None:
        if self._buffer:
            self._write_line(bytes(self._buffer))
            self._buffer.clear()

    def _drain_lines(self) -> None:
        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index < 0:
                return
            line = bytes(self._buffer[: newline_index + 1])
            del self._buffer[: newline_index + 1]
            self._write_line(line)

    def _write_line(self, line: bytes) -> None:
        text = line.decode("utf-8", errors="replace")
        payload = _json_object_line(text)
        if payload is not None:
            self._events_handle.write(text)
            if not text.endswith("\n"):
                self._events_handle.write("\n")
            self._events_handle.flush()
            if looks_like_openhands_step(payload):
                self.assistant_steps += 1
                if self._max_steps is not None and self.assistant_steps > self._max_steps:
                    self.step_limit_exceeded = True
            return
        self._stdout_handle.write(text)
        if not text.endswith("\n"):
            self._stdout_handle.write("\n")
        self._stdout_handle.flush()

    def close(self) -> None:
        self.flush()
        self._stdout_handle.close()
        self._events_handle.close()


def _json_object_line(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _submission_has_python_files(submission_dir: Path) -> bool:
    return submission_dir.is_dir() and any(submission_dir.rglob("*.py"))


_INFRA_FAILURE_RANK = {
    "invalid_encrypted_content": 3,
    "rate_limited": 2,
    "tool_validation_error": 1,
}


def _classify_openhands_infrastructure_event(
    payload: dict[str, Any],
    *,
    line_number: int,
) -> dict[str, Any] | None:
    kind = str(payload.get("kind") or "")
    if kind == "AgentErrorEvent":
        error = payload.get("error")
        if not isinstance(error, str) or "error validating tool" not in error.lower():
            return None
        return {
            "schema_version": "featureliftbench.openhands_infrastructure_error.v1",
            "failure_class": "tool_validation_error",
            "retryable": True,
            "event_id": str(payload.get("id") or ""),
            "event_line": line_number,
            "tool_name": str(payload.get("tool_name") or ""),
            "error": error[:2000],
        }
    if kind != "ConversationErrorEvent":
        return None
    detail_parts = [
        str(payload.get("code") or ""),
        str(payload.get("detail") or ""),
        str(payload.get("error") or ""),
        str(payload.get("message") or ""),
    ]
    text = "\n".join(detail_parts)
    lowered = text.lower()
    if any(
        needle in lowered
        for needle in (
            "invalid_encrypted",
            "encrypted content could not",
            "could not be decrypted",
            "encrypted content for item",
        )
    ):
        failure_class = "invalid_encrypted_content"
    elif "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        failure_class = "rate_limited"
    else:
        return None
    return {
        "schema_version": "featureliftbench.openhands_infrastructure_error.v1",
        "failure_class": failure_class,
        "retryable": True,
        "event_id": str(payload.get("id") or ""),
        "event_line": line_number,
        "tool_name": str(payload.get("tool_name") or ""),
        "error": text[:2000],
    }


def _detect_openhands_infrastructure_error(
    events_path: Path | None,
) -> dict[str, Any] | None:
    """Return an auditable OpenHands infrastructure error from JSONL events.

    OpenHands can emit an ``AgentErrorEvent`` for an invalid tool-call payload,
    print a goodbye message, and still exit zero. An empty submission plus that
    event is not a successful agent completion. A later recovered run that still
    wrote Python under ``submission/`` is recorded here but not failed.

    Provider protocol flakes such as OpenLux ``invalid_encrypted_content`` arrive
    as ``ConversationErrorEvent`` and are ranked above tool-validation noise when
    both appear in the same trajectory.
    """

    if events_path is None or not events_path.is_file():
        return None
    try:
        lines = events_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    best: dict[str, Any] | None = None
    best_rank = -1
    for line_number, line in enumerate(lines, start=1):
        payload = _json_object_line(line)
        if payload is None:
            continue
        classified = _classify_openhands_infrastructure_event(
            payload, line_number=line_number
        )
        if classified is None:
            continue
        rank = _INFRA_FAILURE_RANK.get(str(classified.get("failure_class") or ""), 0)
        if rank >= best_rank:
            best = classified
            best_rank = rank
    return best


def _openhands_max_steps(env: dict[str, str]) -> int | None:
    raw = env.get("FEATURELIFTBENCH_OPENHANDS_MAX_STEPS", "120").strip()
    if not raw:
        return 120
    try:
        parsed = int(raw)
    except ValueError:
        return 120
    return parsed if parsed > 0 else None


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except (PermissionError, OSError):
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _write_command_record(
    config: OpenHandsRunnerConfig,
    *,
    prompt_file: Path,
    command_template: str,
    command: list[str],
    configured: bool,
    error: str,
) -> None:
    payload = {
        "runtime": "openhands",
        "configured": configured,
        "command_template": _redact_text(command_template),
        "command": _redact_command(command),
        "cwd": str(config.workspace_dir),
        "prompt_file": str(prompt_file),
        "model": config.model,
        "error": error,
        "placeholders": [
            "workspace",
            "task_file",
            "submission_dir",
            "agent_output_dir",
            "prompt_file",
            "model",
            "python",
        ],
    }
    (config.agent_output_dir / "openhands_command.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_raw_usage(agent_output_dir: Path) -> dict[str, Any] | None:
    for filename in RAW_USAGE_FILENAMES:
        path = agent_output_dir / filename
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _merge_compression_audit(
    raw_usage: dict[str, Any] | None,
    compression: dict[str, int],
) -> dict[str, Any]:
    merged = dict(raw_usage) if raw_usage is not None else {}
    existing = merged.get("context_audit")
    context = dict(existing) if isinstance(existing, dict) else {}
    if raw_usage is None:
        context.update(
            {
                "available": False,
                "usage_unverified": True,
                "token_source": "events_without_token_usage",
            }
        )
    context.update(compression)
    merged["context_audit"] = context
    return merged


def _write_usage(
    config: OpenHandsRunnerConfig,
    *,
    exit_status: str,
    returncode: int,
    duration_seconds: float,
    raw_usage: dict[str, Any] | None,
    assistant_steps: int = 0,
    infrastructure_error: dict[str, Any] | None = None,
) -> None:
    metrics = _usage_metrics(raw_usage)
    if assistant_steps > metrics.get("assistant_steps", 0):
        metrics["assistant_steps"] = assistant_steps
    context_audit = _usage_context_audit(raw_usage)
    payload: dict[str, Any] = {
        "schema_version": USAGE_SCHEMA_VERSION,
        "agent_name": "openhands-agent",
        "model": config.model,
        "available": True,
        "assistant_steps": metrics.get("assistant_steps", 0),
        "api_calls": metrics.get("api_calls", 0),
        "prompt_tokens": metrics.get("prompt_tokens", 0),
        "completion_tokens": metrics.get("completion_tokens", 0),
        "total_tokens": metrics.get("total_tokens", 0),
        "prompt_cache_accounting_available": bool(
            raw_usage.get("prompt_cache_accounting_available", False)
            if isinstance(raw_usage, dict)
            else False
        ),
        "prompt_cache_hit_tokens": metrics.get("prompt_cache_hit_tokens", 0),
        "prompt_cache_miss_tokens": metrics.get("prompt_cache_miss_tokens", 0),
        "effective_uncached_prompt_tokens": metrics.get(
            "effective_uncached_prompt_tokens", 0
        ),
        "tool_alias_normalizations": metrics.get("tool_alias_normalizations", 0),
        "context_audit": context_audit,
        "exit_status": exit_status,
        "external_returncode": returncode,
        "duration_seconds": round(duration_seconds, 6),
    }
    if infrastructure_error is not None:
        payload["infrastructure_error"] = infrastructure_error
    for key in ("trace_tokens", "billed_tokens"):
        if key in metrics:
            payload[key] = metrics[key]
    (config.agent_output_dir / "usage.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _usage_metrics(raw_usage: dict[str, Any] | None) -> dict[str, int]:
    source: dict[str, Any] = {}
    if isinstance(raw_usage, dict):
        nested = raw_usage.get("usage")
        source = nested if isinstance(nested, dict) else raw_usage

    metrics: dict[str, int] = {}
    for key in (
        "assistant_steps",
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
    ):
        value = _int_metric(source.get(key))
        if value is not None:
            metrics[key] = value
    if "total_tokens" not in metrics and (
        "prompt_tokens" in metrics or "completion_tokens" in metrics
    ):
        metrics["total_tokens"] = metrics.get("prompt_tokens", 0) + metrics.get(
            "completion_tokens",
            0,
        )
    return metrics


def _usage_context_audit(raw_usage: dict[str, Any] | None) -> dict[str, Any]:
    raw_context: dict[str, Any] = {}
    if isinstance(raw_usage, dict) and isinstance(raw_usage.get("context_audit"), dict):
        raw_context = raw_usage["context_audit"]
    raw_available = raw_context.get("available")
    context_available = raw_available if isinstance(raw_available, bool) else bool(raw_context)
    limits = openhands_context_limits()
    try:
        policy_fields = context_policy_audit_fields()
    except ValueError:
        policy_fields = {
            "compression_mode": os.environ.get(CONDENSER_MODE_ENV, "invalid"),
        }

    audit: dict[str, Any] = {
        "available": context_available,
        "history_policy": str(raw_context.get("history_policy") or "external_openhands"),
        "over_context_behavior": str(
            raw_context.get("over_context_behavior") or "managed_by_openhands"
        ),
        "token_source": str(
            raw_context.get("token_source")
            or ("openhands_usage_file" if raw_usage else "unavailable")
        ),
        "runtime": str(raw_context.get("runtime") or "openhands"),
        "context_violation": bool(raw_context.get("context_violation", False)),
        "usage_unverified": bool(raw_context.get("usage_unverified", True)),
        "context_window_tokens": limits.context_window_tokens,
        "reserved_output_tokens": limits.reserved_output_tokens,
        "max_allowed_prompt_tokens": limits.max_allowed_prompt_tokens,
        **policy_fields,
        "condensation_events": 0,
        "forgotten_event_count": 0,
        "condensation_summaries_nonempty": 0,
    }
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
        "condensation_events",
        "forgotten_event_count",
        "condensation_summaries_nonempty",
    ):
        value = _int_metric(raw_context.get(key))
        if value is not None:
            audit[key] = value
    compression_mode = raw_context.get("compression_mode")
    if isinstance(compression_mode, str) and compression_mode:
        audit["compression_mode"] = compression_mode
    return audit


def _int_metric(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _redact_command(command: list[str]) -> list[str]:
    return [_redact_text(item) for item in command]


def _redact_text(text: str) -> str:
    redacted = text
    for value in _secret_values():
        if value and value in redacted:
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def _secret_values() -> set[str]:
    values: set[str] = set()
    for key, value in os.environ.items():
        upper = key.upper()
        if any(marker in upper for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            if len(value) >= 6:
                values.add(value)
    return values


if __name__ == "__main__":
    raise SystemExit(main())
