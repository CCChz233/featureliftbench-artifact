"""FeatureLiftBench-native agent controller.

This is the first integration point for the planned FeatureLiftAgent protocol.
It intentionally starts as a small controller scaffold: it writes durable state
files and usage/context audit artifacts, then creates a minimal submission
package. Model calls and the OpenHands SDK tool runtime will be added behind
this command contract.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from .dependency_install import install_dependency_lock

USAGE_SCHEMA_VERSION = "featureliftbench.agent_usage.v1"
DEFAULT_CONTEXT_WINDOW_TOKENS = 131_072
DEFAULT_RESERVED_OUTPUT_TOKENS = 8_192
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_TOOL_TIMEOUT_SECONDS = 60
DEFAULT_MAX_OBSERVATION_CHARS = 12_000
DEFAULT_MAX_REPAIR_ROUNDS = 1
VALID_LLM_PHASES = ("closure_plan", "extraction_plan", "final_checklist", "repair_plan")
AGENT_TOOL_VENV_DIRNAME = ".featurelift-agent-venv"
_AGENT_TOOL_VENV_READY: set[str] = set()
PHASE_OUTPUT_FILES = {
    "closure_plan": "closure_plan.md",
    "extraction_plan": "extraction_plan.md",
    "final_checklist": "final_checklist.md",
    "repair_plan": "repair_plan.md",
}


@dataclass(frozen=True)
class FeatureLiftAgentConfig:
    workspace: Path
    task_file: Path
    submission_dir: Path
    agent_output_dir: Path
    model: str
    context_window_tokens: int
    reserved_output_tokens: int
    runtime: str
    enable_llm: bool
    api_base: str
    api_key: str
    request_timeout_seconds: int
    max_tokens: int
    llm_phases: tuple[str, ...] = ("closure_plan",)
    execute_actions: bool = False
    tool_timeout_seconds: int = DEFAULT_TOOL_TIMEOUT_SECONDS
    max_observation_chars: int = DEFAULT_MAX_OBSERVATION_CHARS
    max_repair_rounds: int = DEFAULT_MAX_REPAIR_ROUNDS

    @property
    def max_allowed_prompt_tokens(self) -> int:
        return max(0, self.context_window_tokens - self.reserved_output_tokens)


@dataclass(frozen=True)
class LlmCallResult:
    content: str
    audit_record: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    usage_unverified: bool


class FeatureLiftAgentError(RuntimeError):
    """Controlled FeatureLiftAgent runtime error."""


class ContextBudgetError(FeatureLiftAgentError):
    """Raised before an LLM call would exceed the configured context budget."""

    def __init__(self, message: str, audit_record: dict[str, Any]) -> None:
        super().__init__(message)
        self.audit_record = audit_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="featureliftbench.featurelift_agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run FeatureLiftAgent on a prepared workspace")
    run_parser.add_argument("--workspace", type=Path, default=_env_path("FEATURELIFTBENCH_WORKSPACE"))
    run_parser.add_argument("--task-file", type=Path, default=_env_path("FEATURELIFTBENCH_TASK_FILE"))
    run_parser.add_argument(
        "--submission-dir",
        type=Path,
        default=_env_path("FEATURELIFTBENCH_SUBMISSION_DIR"),
    )
    run_parser.add_argument(
        "--agent-output-dir",
        type=Path,
        default=_env_path("FEATURELIFTBENCH_AGENT_OUTPUT_DIR"),
    )
    run_parser.add_argument(
        "--model",
        default=os.environ.get("FEATURELIFTBENCH_MODEL", ""),
        help="model identifier; stored in usage.json for audit",
    )
    run_parser.add_argument(
        "--context-window",
        type=int,
        default=_env_int("FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS", DEFAULT_CONTEXT_WINDOW_TOKENS),
    )
    run_parser.add_argument(
        "--reserved-output",
        type=int,
        default=_env_int("FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS", DEFAULT_RESERVED_OUTPUT_TOKENS),
    )
    run_parser.add_argument(
        "--runtime",
        default=os.environ.get("FEATURELIFTBENCH_FEATURELIFT_RUNTIME", "scaffold"),
        choices=("scaffold", "openhands"),
        help="agent runtime backend; openhands is reserved for the next integration step",
    )
    run_parser.add_argument(
        "--enable-llm",
        action="store_true",
        default=_env_truthy("FEATURELIFTBENCH_FEATURELIFT_ENABLE_LLM"),
        help="perform the first context-audited OpenAI-compatible model call",
    )
    run_parser.add_argument(
        "--api-base",
        default=_first_env(
            "FEATURELIFTBENCH_API_BASE",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
        ),
        help="OpenAI-compatible API base URL",
    )
    run_parser.add_argument(
        "--api-key",
        default=_first_env(
            "FEATURELIFTBENCH_API_KEY",
            "OPENAI_API_KEY",
            "LITELLM_API_KEY",
        ),
        help="OpenAI-compatible API key; normally supplied through env",
    )
    run_parser.add_argument(
        "--request-timeout",
        type=int,
        default=_env_int("FEATURELIFTBENCH_FEATURELIFT_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT_SECONDS),
        help="HTTP request timeout in seconds for model calls",
    )
    run_parser.add_argument(
        "--max-tokens",
        type=int,
        default=_env_int("FEATURELIFTBENCH_FEATURELIFT_MAX_TOKENS", 0),
        help="model completion max_tokens; defaults to reserved output budget",
    )
    run_parser.add_argument(
        "--llm-phases",
        default=os.environ.get("FEATURELIFTBENCH_FEATURELIFT_LLM_PHASES", "closure_plan"),
        help=(
            "comma-separated model phases to run when --enable-llm is set; "
            f"allowed: {', '.join(VALID_LLM_PHASES)}"
        ),
    )
    run_parser.add_argument(
        "--execute-actions",
        action="store_true",
        default=_env_truthy("FEATURELIFTBENCH_FEATURELIFT_EXECUTE_ACTIONS"),
        help="execute parsed phase actions through the bounded local tool executor",
    )
    run_parser.add_argument(
        "--tool-timeout",
        type=int,
        default=_env_int("FEATURELIFTBENCH_FEATURELIFT_TOOL_TIMEOUT", DEFAULT_TOOL_TIMEOUT_SECONDS),
        help="timeout in seconds for controlled tool commands such as public tests",
    )
    run_parser.add_argument(
        "--max-observation-chars",
        type=int,
        default=_env_int("FEATURELIFTBENCH_FEATURELIFT_MAX_OBSERVATION_CHARS", DEFAULT_MAX_OBSERVATION_CHARS),
        help="maximum characters recorded per tool observation",
    )
    run_parser.add_argument(
        "--max-repair-rounds",
        type=int,
        default=_env_int("FEATURELIFTBENCH_FEATURELIFT_MAX_REPAIR_ROUNDS", DEFAULT_MAX_REPAIR_ROUNDS),
        help="maximum repair-plan model calls after failed tool observations",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            llm_phases = _parse_llm_phases(args.llm_phases)
        except ValueError as exc:
            parser.error(str(exc))
        return run(
            FeatureLiftAgentConfig(
                workspace=args.workspace.resolve(),
                task_file=args.task_file.resolve(),
                submission_dir=args.submission_dir.resolve(),
                agent_output_dir=args.agent_output_dir.resolve(),
                model=args.model,
                context_window_tokens=args.context_window,
                reserved_output_tokens=args.reserved_output,
                runtime=args.runtime,
                enable_llm=args.enable_llm,
                api_base=args.api_base,
                api_key=args.api_key,
                request_timeout_seconds=args.request_timeout,
                max_tokens=args.max_tokens or args.reserved_output,
                llm_phases=llm_phases,
                execute_actions=args.execute_actions,
                tool_timeout_seconds=args.tool_timeout,
                max_observation_chars=args.max_observation_chars,
                max_repair_rounds=args.max_repair_rounds,
            )
        )
    parser.error(f"unknown command: {args.command}")
    return 2


def run(config: FeatureLiftAgentConfig) -> int:
    config.agent_output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = config.agent_output_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    task_text = _read_text(config.task_file)
    prompt_tokens = _cheap_token_estimate(task_text)
    over_context = prompt_tokens > config.max_allowed_prompt_tokens
    bootstrap_audit_record = {
        "call_index": 0,
        "phase": "bootstrap",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": 0,
        "total_tokens": prompt_tokens,
        "context_window_tokens": config.context_window_tokens,
        "reserved_output_tokens": config.reserved_output_tokens,
        "max_allowed_prompt_tokens": config.max_allowed_prompt_tokens,
        "over_context": over_context,
        "token_source": "estimated_chars_div4",
        "prompt_sha256": hashlib.sha256(task_text.encode("utf-8")).hexdigest(),
        "runtime": config.runtime,
        "is_model_call": False,
    }
    audit_records = [bootstrap_audit_record]
    usage_totals = {
        "assistant_steps": 0,
        "total_messages": 0,
        "api_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    tool_observations: list[dict[str, Any]] = []

    _write_state_files(config, state_dir, task_text)

    if over_context:
        _write_context_audit(config.agent_output_dir / "context_audit.jsonl", audit_records)
        _write_usage(
            config,
            available=True,
            context_violation=True,
            audit_records=audit_records,
            usage_totals=usage_totals,
            exit_status="context_violation",
            tool_observations=tool_observations,
        )
        print(
            "FeatureLiftAgent refused to start: bootstrap prompt exceeds configured context budget",
            file=sys.stderr,
        )
        return 2

    if config.enable_llm:
        llm_results: list[LlmCallResult] = []
        next_call_index = 1
        try:
            for phase in config.llm_phases:
                llm_result = _run_llm_phase(
                    config,
                    state_dir,
                    phase=phase,
                    call_index=next_call_index,
                )
                next_call_index += 1
                llm_results.append(llm_result)
                audit_records.append(llm_result.audit_record)
                _append_phase_output(
                    state_dir / PHASE_OUTPUT_FILES[phase],
                    phase,
                    llm_result.content,
                )
                if config.execute_actions:
                    new_observations = _execute_phase_actions(config, state_dir, phase)
                    tool_observations.extend(new_observations)
                    repair_round = 0
                    while (
                        repair_round < max(0, config.max_repair_rounds)
                        and _tool_observations_need_repair(new_observations)
                    ):
                        repair_round += 1
                        _write_repair_context(state_dir, phase, repair_round, new_observations)
                        repair_result = _run_llm_phase(
                            config,
                            state_dir,
                            phase="repair_plan",
                            call_index=next_call_index,
                        )
                        next_call_index += 1
                        llm_results.append(repair_result)
                        audit_records.append(repair_result.audit_record)
                        _append_phase_output(
                            state_dir / PHASE_OUTPUT_FILES["repair_plan"],
                            "repair_plan",
                            repair_result.content,
                        )
                        new_observations = _execute_phase_actions(config, state_dir, "repair_plan")
                        tool_observations.extend(new_observations)
        except ContextBudgetError as exc:
            audit_records.append(exc.audit_record)
            usage_totals = _usage_totals_from_llm_results(llm_results)
            _write_context_audit(config.agent_output_dir / "context_audit.jsonl", audit_records)
            _write_usage(
                config,
                available=True,
                context_violation=True,
                audit_records=audit_records,
                usage_totals=usage_totals,
                exit_status="context_violation",
                tool_observations=tool_observations,
            )
            print(str(exc), file=sys.stderr)
            return 2
        except FeatureLiftAgentError as exc:
            usage_totals = _usage_totals_from_llm_results(llm_results)
            (state_dir / "llm_error.md").write_text(f"# LLM Error\n\n{exc}\n", encoding="utf-8")
            _write_context_audit(config.agent_output_dir / "context_audit.jsonl", audit_records)
            _write_usage(
                config,
                available=True,
                context_violation=False,
                audit_records=audit_records,
                usage_totals=usage_totals,
                exit_status="llm_error",
                tool_observations=tool_observations,
            )
            print(str(exc), file=sys.stderr)
            return 2
        usage_totals = _usage_totals_from_llm_results(llm_results)

    _write_context_audit(config.agent_output_dir / "context_audit.jsonl", audit_records)
    _create_submission_scaffold(config.submission_dir)
    native_stopping_guard = _repo_graph_native_stopping_guard(config)
    exit_status = _completed_exit_status(config, tool_observations)
    stopping_blocked = bool(
        config.execute_actions
        and native_stopping_guard is not None
        and not native_stopping_guard.get("ready", False)
    )
    if stopping_blocked:
        exit_status = "stopping_guard_blocked"
    _write_usage(
        config,
        available=True,
        context_violation=False,
        audit_records=audit_records,
        usage_totals=usage_totals,
        exit_status=exit_status,
        tool_observations=tool_observations,
    )
    print("FeatureLiftAgent scaffold initialized")
    if config.enable_llm:
        print(f"Completed {usage_totals.get('api_calls', 0)} context-audited LLM phase call(s).")
    else:
        print("Runtime model calls are disabled; wrote protocol artifacts only.")
    if stopping_blocked:
        print("FeatureLiftAgent stopping guard blocked finalization", file=sys.stderr)
        return 3
    return 0


def _run_bootstrap_llm_call(config: FeatureLiftAgentConfig, state_dir: Path) -> LlmCallResult:
    return _run_llm_phase(config, state_dir, phase="closure_plan", call_index=1)


def _run_llm_phase(
    config: FeatureLiftAgentConfig,
    state_dir: Path,
    *,
    phase: str,
    call_index: int,
) -> LlmCallResult:
    if not config.model:
        raise FeatureLiftAgentError("--enable-llm requires --model or FEATURELIFTBENCH_MODEL")
    if not config.api_base:
        raise FeatureLiftAgentError("--enable-llm requires --api-base or FEATURELIFTBENCH_API_BASE/OPENAI_BASE_URL")
    if not config.api_key:
        raise FeatureLiftAgentError("--enable-llm requires --api-key or FEATURELIFTBENCH_API_KEY/OPENAI_API_KEY")

    if phase not in VALID_LLM_PHASES:
        raise FeatureLiftAgentError(f"unknown LLM phase: {phase}")
    system_prompt, user_prompt = _build_phase_prompt(state_dir, phase)
    prompt_text = system_prompt + "\n\n" + user_prompt
    prompt_tokens_estimate = _cheap_token_estimate(prompt_text)
    over_context = prompt_tokens_estimate > config.max_allowed_prompt_tokens
    audit_record = {
        "call_index": call_index,
        "phase": phase,
        "prompt_tokens": prompt_tokens_estimate,
        "completion_tokens": 0,
        "total_tokens": prompt_tokens_estimate,
        "context_window_tokens": config.context_window_tokens,
        "reserved_output_tokens": config.reserved_output_tokens,
        "max_allowed_prompt_tokens": config.max_allowed_prompt_tokens,
        "over_context": over_context,
        "token_source": "estimated_chars_div4",
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "runtime": config.runtime,
        "is_model_call": True,
        "model": config.model,
    }
    api_model = _api_model_name(config)
    if api_model != config.model:
        audit_record["api_model"] = api_model
    if over_context:
        raise ContextBudgetError(
            f"FeatureLiftAgent refused model call: {phase} prompt exceeds configured context budget",
            audit_record,
        )

    response = _post_chat_completion(
        config,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = _extract_chat_content(response)
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    prompt_tokens = _int_or_none(usage.get("prompt_tokens")) or prompt_tokens_estimate
    completion_tokens = _int_or_none(usage.get("completion_tokens")) or _cheap_token_estimate(content)
    total_tokens = _int_or_none(usage.get("total_tokens")) or prompt_tokens + completion_tokens
    usage_unverified = not isinstance(response.get("usage"), dict)

    audit_record.update(
        {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "token_source": "provider_usage" if not usage_unverified else "estimated_chars_div4",
            "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
    )
    response_id = response.get("id")
    if isinstance(response_id, str):
        audit_record["response_id"] = response_id
    return LlmCallResult(
        content=content,
        audit_record=audit_record,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        usage_unverified=usage_unverified,
    )


def _build_bootstrap_llm_prompt(state_dir: Path) -> tuple[str, str]:
    return _build_phase_prompt(state_dir, "closure_plan")


def _build_phase_prompt(state_dir: Path, phase: str) -> tuple[str, str]:
    system_prompt = (
        "You are FeatureLiftAgent, a code extraction controller for FeatureLiftBench. "
        "Return a concise JSON object followed by optional Markdown notes. "
        "Do not claim tests were run unless the state says they were run. "
        "Do not output final code unless the requested phase explicitly asks for a patch."
    )
    if phase == "closure_plan":
        task = (
            "Draft the first closure plan. Identify runtime files to inspect, likely resources, "
            "hidden-risk behaviors, and first actions."
        )
        context = (
            "## task_brief.md\n"
            f"{_read_text(state_dir / 'task_brief.md')}\n\n"
            f"{_source_hint_phase_context(state_dir)}"
            "## repo_map.md\n"
            f"{_read_text(state_dir / 'repo_map.md')}\n"
            f"{_repo_graph_phase_context(state_dir)}"
        )
    elif phase == "extraction_plan":
        task = (
            "Turn the closure plan into a concrete extraction plan. List files to copy or write, "
            "imports to rewrite, package files to create, and public checks to run."
        )
        context = (
            "## closure_plan.md\n"
            f"{_read_text(state_dir / 'closure_plan.md')}\n\n"
            "## extraction_log.md\n"
            f"{_read_text(state_dir / 'extraction_log.md')}\n\n"
            "## dependency_manifest.json\n"
            f"{_read_text(state_dir / 'dependency_manifest.json')}\n"
        )
    elif phase == "final_checklist":
        task = (
            "Draft the final pre-submit checklist. Include output API checks, forbidden import checks, "
            "public-test checks, hidden-boundary risks, and footprint pruning checks."
        )
        context = (
            "## extraction_plan.md\n"
            f"{_read_text(state_dir / 'extraction_plan.md')}\n\n"
            "## hidden_boundary_check.md\n"
            f"{_read_text(state_dir / 'hidden_boundary_check.md')}\n\n"
            "## test_log.md\n"
            f"{_read_text(state_dir / 'test_log.md')}\n"
        )
    elif phase == "repair_plan":
        task = (
            "Repair the failed or blocked tool observations. Use the smallest bounded action sequence "
            "that can make public tests and final checks pass without hidden-test access."
        )
        context = (
            "## repair_context.json\n"
            f"{_read_text(state_dir / 'repair_context.json')}\n\n"
            "## tool_observations.jsonl\n"
            f"{_read_text(state_dir / 'tool_observations.jsonl')}\n\n"
            "## extraction_log.md\n"
            f"{_read_text(state_dir / 'extraction_log.md')}\n\n"
            "## test_log.md\n"
            f"{_read_text(state_dir / 'test_log.md')}\n\n"
            "## final_checklist.md\n"
            f"{_read_text(state_dir / 'final_checklist.md')}\n"
        )
    else:
        raise FeatureLiftAgentError(f"unknown LLM phase: {phase}")
    graph_enabled = (state_dir / "repo_graph" / "base" / "manifest.json").is_file()
    evidence_enabled = (state_dir / "repo_graph" / "semantic_claims.jsonl").is_file()
    if evidence_enabled:
        allowed_action_types = "inspect_file|copy_file|write_file|repo_graph_query|repo_graph_claim|run_public_tests|prune_submission|final_check"
    elif graph_enabled:
        allowed_action_types = "inspect_file|copy_file|write_file|repo_graph_query|run_public_tests|prune_submission|final_check"
    else:
        allowed_action_types = "inspect_file|copy_file|write_file|run_public_tests|prune_submission|final_check"
    user_prompt = (
        f"Phase: {phase}\n\n"
        f"Task: {task}\n\n"
        "Return JSON matching this schema, then optional Markdown notes:\n\n"
        "```json\n"
        "{\n"
        f'  "phase": "{phase}",\n'
        '  "summary": "one paragraph",\n'
        '  "actions": [\n'
        f'    {{"type": "{allowed_action_types}", "target": "path or check name", "reason": "why"}}\n'
        "  ],\n"
        '  "risks": ["risk or unknown"]\n'
        "}\n"
        "```\n\n"
        "For copy_file actions, include source and destination when target is ambiguous. "
        "For write_file actions, include content. "
        "Allowed action types are defined in action_schema.json. Do not invent hidden-test access.\n\n"
        "## action_schema.json\n"
        f"{_read_text(state_dir / 'action_schema.json')}\n\n"
        f"{context}"
    )
    return system_prompt, user_prompt


def _post_chat_completion(config: FeatureLiftAgentConfig, *, messages: list[dict[str, str]]) -> dict[str, Any]:
    url = _chat_completions_url(config.api_base)
    payload = {
        "model": _api_model_name(config),
        "messages": messages,
        "temperature": 0,
        "max_tokens": config.max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.request_timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise FeatureLiftAgentError(f"model API HTTP {exc.code}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise FeatureLiftAgentError(f"model API request failed: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeatureLiftAgentError(f"model API returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise FeatureLiftAgentError("model API response must be a JSON object")
    return data


def _chat_completions_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _api_model_name(config: FeatureLiftAgentConfig) -> str:
    if "api.deepseek.com" in config.api_base and config.model.startswith("deepseek/"):
        return config.model.split("/", 1)[1]
    return config.model


def _extract_chat_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise FeatureLiftAgentError("model API response did not contain choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise FeatureLiftAgentError("model API choice must be an object")
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    text = first.get("text")
    if isinstance(text, str):
        return text
    raise FeatureLiftAgentError("model API response did not contain message content")


def _append_phase_output(path: Path, phase: str, content: str) -> None:
    parsed_action = _extract_json_object_from_text(content)
    parsed_path = path.with_suffix(".json")
    if parsed_action is not None:
        parsed_path.write_text(
            json.dumps(parsed_action, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n\n## LLM {phase.replace('_', ' ').title()}\n\n")
        handle.write(content.strip())
        handle.write("\n")


def _usage_totals_from_llm_results(results: list[LlmCallResult]) -> dict[str, int]:
    return {
        "assistant_steps": len(results),
        "total_messages": len(results) * 2,
        "api_calls": len(results),
        "prompt_tokens": sum(result.prompt_tokens for result in results),
        "completion_tokens": sum(result.completion_tokens for result in results),
        "total_tokens": sum(result.total_tokens for result in results),
    }


def _execute_phase_actions(config: FeatureLiftAgentConfig, state_dir: Path, phase: str) -> list[dict[str, Any]]:
    phase_json_path = (state_dir / PHASE_OUTPUT_FILES[phase]).with_suffix(".json")
    if not phase_json_path.is_file():
        return []
    phase_data = _read_json_object(phase_json_path)
    actions = phase_data.get("actions")
    if not isinstance(actions, list):
        return []

    observations = []
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            observation = _tool_observation(
                phase=phase,
                action_index=index,
                action_type="invalid",
                target="",
                reason="",
                status="blocked",
                summary="action must be a JSON object",
            )
        else:
            observation = _execute_action(config, phase, index, action)
        observations.append(observation)
        _append_tool_observation(state_dir, observation)
    return observations


def _tool_observations_need_repair(observations: list[dict[str, Any]]) -> bool:
    return any(
        observation.get("status") in {"failed", "blocked", "timeout", "error"}
        for observation in observations
    )


def _write_repair_context(
    state_dir: Path,
    failed_phase: str,
    repair_round: int,
    observations: list[dict[str, Any]],
) -> None:
    payload = {
        "schema_version": "featureliftbench.repair_context.v1",
        "failed_phase": failed_phase,
        "repair_round": repair_round,
        "failed_observations": [
            observation
            for observation in observations
            if observation.get("status") in {"failed", "blocked", "timeout", "error"}
        ],
    }
    (state_dir / "repair_context.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _execute_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    action_type = _action_text_field(action, "type")
    target = _action_text_field(action, "target")
    reason = _action_text_field(action, "reason")
    graph_enabled = (
        config.agent_output_dir / "state" / "repo_graph" / "base" / "manifest.json"
    ).is_file()
    evidence_enabled = (
        config.agent_output_dir / "state" / "repo_graph" / "semantic_claims.jsonl"
    ).is_file()
    if action_type not in _action_schema(
        repo_graph_enabled=graph_enabled,
        repo_graph_evidence_enabled=evidence_enabled,
    )["action_types"]:
        return _tool_observation(
            phase=phase,
            action_index=action_index,
            action_type=action_type or "missing",
            target=target,
            reason=reason,
            status="blocked",
            summary="unknown or missing action type",
        )
    try:
        if action_type == "inspect_file":
            return _inspect_file_action(config, phase, action_index, action)
        if action_type == "copy_file":
            return _copy_file_action(config, phase, action_index, action)
        if action_type == "write_file":
            return _write_file_action(config, phase, action_index, action)
        if action_type == "repo_graph_query":
            return _repo_graph_query_action(config, phase, action_index, action)
        if action_type == "repo_graph_claim":
            return _repo_graph_claim_action(config, phase, action_index, action)
        if action_type == "run_public_tests":
            return _run_public_tests_action(config, phase, action_index, action)
        if action_type == "prune_submission":
            return _prune_submission_action(config, phase, action_index, action)
        if action_type == "final_check":
            return _final_check_action(config, phase, action_index, action)
    except FeatureLiftAgentError as exc:
        return _tool_observation(
            phase=phase,
            action_index=action_index,
            action_type=action_type,
            target=target,
            reason=reason,
            status="blocked",
            summary=str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive guard for tool failures
        return _tool_observation(
            phase=phase,
            action_index=action_index,
            action_type=action_type,
            target=target,
            reason=reason,
            status="error",
            summary=f"{type(exc).__name__}: {exc}",
        )
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type=action_type,
        target=target,
        reason=reason,
        status="blocked",
        summary="action type is declared but has no executor",
    )


def _inspect_file_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    target = _action_text_field(action, "target", "source")
    reason = _action_text_field(action, "reason")
    path = _resolve_readable_workspace_path(config, target)
    if not path.is_file():
        return _tool_observation(
            phase=phase,
            action_index=action_index,
            action_type="inspect_file",
            target=target,
            reason=reason,
            status="blocked",
            summary="target is not a file",
        )
    content, truncated = _read_bounded_file(path, config.max_observation_chars)
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="inspect_file",
        target=_workspace_relative(config, path),
        reason=reason,
        status="success",
        summary=f"read {len(content)} character(s)" + ("; truncated" if truncated else ""),
        output=content,
        truncated=truncated,
    )


def _copy_file_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    source_raw = _action_text_field(action, "source", "target")
    destination_raw = _action_text_field(action, "destination")
    reason = _action_text_field(action, "reason")
    source = _resolve_readable_workspace_path(config, source_raw)
    if not source.is_file() and not source.is_dir():
        return _tool_observation(
            phase=phase,
            action_index=action_index,
            action_type="copy_file",
            target=source_raw,
            reason=reason,
            status="blocked",
            summary="source is not a file",
        )
    destination = _resolve_submission_path(
        config,
        destination_raw or f"featurelifted/{source.name}",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)
    _prune_submission_transients(config.submission_dir)
    _sync_repo_graph_after_mutation(config)
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="copy_file",
        target=f"{_workspace_relative(config, source)} -> {_workspace_relative(config, destination)}",
        reason=reason,
        status="success",
        summary=(
            f"copied directory with {_count_files(source)} file(s)"
            if source.is_dir()
            else f"copied {source.stat().st_size} byte(s)"
        ),
    )


def _write_file_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    target = _action_text_field(action, "target", "destination")
    reason = _action_text_field(action, "reason")
    content = action.get("content")
    if not isinstance(content, str):
        return _tool_observation(
            phase=phase,
            action_index=action_index,
            action_type="write_file",
            target=target,
            reason=reason,
            status="blocked",
            summary="write_file requires string content",
        )
    destination = _resolve_submission_path(config, target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    _prune_submission_transients(config.submission_dir)
    _sync_repo_graph_after_mutation(config)
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="write_file",
        target=_workspace_relative(config, destination),
        reason=reason,
        status="success",
        summary=f"wrote {len(content)} character(s)",
    )


def _repo_graph_query_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    reason = _action_text_field(action, "reason")
    command = _action_text_field(action, "command")
    target = _action_text_field(action, "target", "query", "node")
    graph_root = config.agent_output_dir / "state" / "repo_graph"
    if not (graph_root / "base" / "manifest.json").is_file():
        raise FeatureLiftAgentError("repository graph is not enabled for this run")
    allowed = {
        "bootstrap",
        "search",
        "inspect",
        "support",
        "paths",
        "closure",
        "risks",
        "self-check",
        "task-closure",
        "sync-submission",
        "compare",
        "detectors",
        "freshness",
        "stopping-check",
        "claim-list",
        "evidence-list",
    }
    if command not in allowed:
        raise FeatureLiftAgentError(f"unsupported repository graph command: {command or 'missing'}")
    cli_command = {
        "claim-list": ["claim", "list"],
        "evidence-list": ["evidence", "list"],
    }.get(command, [command])
    argv = [sys.executable, "-m", "featureliftbench.repo_graph.cli", *cli_command]
    if command == "search":
        if not target:
            raise FeatureLiftAgentError("repo_graph_query search requires query or target")
        argv.append(target)
    elif command == "inspect":
        if not target:
            raise FeatureLiftAgentError("repo_graph_query inspect requires node or target")
        argv.append(target)
    elif command == "support":
        seeds = action.get("seeds")
        values = (
            [str(item) for item in seeds if isinstance(item, str) and item]
            if isinstance(seeds, list)
            else ([target] if target else [])
        )
        if not values:
            raise FeatureLiftAgentError("repo_graph_query support requires seeds or target")
        for seed in values:
            argv.extend(["--seed", seed])
        budget = action.get("budget_tokens")
        if isinstance(budget, int) and budget > 0:
            argv.extend(["--budget-tokens", str(budget)])
    elif command == "paths":
        source = _action_text_field(action, "source")
        destination = _action_text_field(action, "destination")
        if not source or not destination:
            raise FeatureLiftAgentError("repo_graph_query paths requires source and destination")
        argv.extend([source, destination])
    elif command == "closure":
        entrypoints = action.get("entrypoints")
        values = (
            [str(item) for item in entrypoints if isinstance(item, str) and item]
            if isinstance(entrypoints, list)
            else ([target] if target else [])
        )
        if not values:
            raise FeatureLiftAgentError("repo_graph_query closure requires entrypoints or target")
        argv.extend(values)
    elif command == "risks" and target:
        argv.append(target)
    env = _tool_env(config)
    env["FEATURELIFTBENCH_REPO_GRAPH_ROOT"] = str(graph_root)
    env["FEATURELIFTBENCH_AGENT_OUTPUT_DIR"] = str(config.agent_output_dir)
    env["FEATURELIFTBENCH_SUBMISSION_DIR"] = str(config.submission_dir)
    env["FEATURELIFTBENCH_WORKSPACE"] = str(config.workspace)
    completed = subprocess.run(
        argv,
        cwd=config.workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=config.tool_timeout_seconds,
        check=False,
    )
    output = _bounded_text(
        (completed.stdout or "") + (completed.stderr or ""),
        config.max_observation_chars,
    )
    repeat_count = _record_repo_graph_query_policy(
        config,
        command=command,
        target=target,
        source=_action_text_field(action, "source"),
        destination=_action_text_field(action, "destination"),
    )
    observation = _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="repo_graph_query",
        target=f"{command} {target}".strip(),
        reason=reason,
        status="success" if completed.returncode == 0 else "failed",
        summary=(
            f"repository graph {command} exited {completed.returncode}"
            + (
                f"; repeated {repeat_count} times without submission revision change"
                if repeat_count > 1
                else ""
            )
        ),
        output=output,
        truncated=len((completed.stdout or "") + (completed.stderr or "")) > config.max_observation_chars,
        returncode=completed.returncode,
    )
    observation["repeat_count_same_revision"] = repeat_count
    observation["action_priority"] = "deprioritized" if repeat_count > 1 else "normal"
    return observation


def _record_repo_graph_query_policy(
    config: FeatureLiftAgentConfig,
    *,
    command: str,
    target: str,
    source: str,
    destination: str,
) -> int:
    graph_root = config.agent_output_dir / "state" / "repo_graph"
    revision_state = _read_json_object(graph_root / "submission_state.json")
    revision = revision_state.get("revision", 0)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "command": command,
                "target": target,
                "source": source,
                "destination": destination,
                "revision": revision,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    path = graph_root / "query_policy.json"
    state = _read_json_object(path)
    counts = state.get("counts") if isinstance(state.get("counts"), dict) else {}
    count = int(counts.get(fingerprint, 0)) + 1
    counts[fingerprint] = count
    path.write_text(
        json.dumps(
            {
                "schema_version": "featureliftbench.repo_graph.query_policy.v1",
                "counts": counts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return count


def _repo_graph_claim_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    if not _repo_graph_evidence_enabled(config):
        raise FeatureLiftAgentError("repository graph evidence mode is not enabled")
    from .repo_graph.ledger import RepoGraphLedger

    ledger = RepoGraphLedger(config.agent_output_dir / "state" / "repo_graph")
    operation = _action_text_field(action, "operation") or "add"
    reason = _action_text_field(action, "reason")
    if operation == "add":
        record = ledger.add_claim(
            subject=_action_text_field(action, "subject", "target"),
            predicate=_action_text_field(action, "predicate"),
            object_value=_action_text_field(action, "object"),
            classification=_action_text_field(action, "classification") or "unresolved",
            confidence=float(action.get("confidence", 0.5)),
        )
    elif operation == "update":
        evidence_ids = action.get("evidence_ids")
        record = ledger.update_claim(
            _action_text_field(action, "claim_id", "target"),
            status=_action_text_field(action, "status"),
            evidence_ids=(
                [str(item) for item in evidence_ids if isinstance(item, str)]
                if isinstance(evidence_ids, list)
                else []
            ),
            classification=_action_text_field(action, "classification") or None,
        )
    else:
        raise FeatureLiftAgentError(f"unsupported repo_graph_claim operation: {operation}")
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="repo_graph_claim",
        target=str(record.get("claim_id", "")),
        reason=reason,
        status="success",
        summary=f"claim {operation} accepted in state {record.get('status', '')}",
        output=json.dumps(record, indent=2, sort_keys=True),
    )


def _run_public_tests_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    reason = _action_text_field(action, "reason")
    _create_submission_scaffold(config.submission_dir)
    _sync_repo_graph_after_mutation(config)
    result = _run_public_tests_command(config)
    _record_repo_graph_tool_evidence(
        config,
        kind="test_result",
        probe_type="public_test_suite",
        evidence_class="public_test",
        status="supports" if result["status"] == "success" else "failed",
        input_summary="run current public tests against current submission revision",
        result_summary=result["summary"],
        command=" ".join(str(item) for item in result.get("command", [])),
    )
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="run_public_tests",
        target="public_tests",
        reason=reason,
        status=result["status"],
        summary=result["summary"],
        output=result["output"],
        returncode=result.get("returncode"),
    )


def _prune_submission_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    reason = _action_text_field(action, "reason")
    removed = _prune_submission_transients(config.submission_dir)
    _sync_repo_graph_after_mutation(config)
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="prune_submission",
        target="submission",
        reason=reason,
        status="success",
        summary=f"removed {len(removed)} transient path(s)",
        output=json.dumps({"removed": removed}, indent=2, sort_keys=True),
    )


def _final_check_action(
    config: FeatureLiftAgentConfig,
    phase: str,
    action_index: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    reason = _action_text_field(action, "reason")
    _create_submission_scaffold(config.submission_dir)
    _sync_repo_graph_after_mutation(config)
    import_probe = subprocess.run(
        [str(_ensure_agent_tool_python(config)), "-c", "import featurelifted"],
        cwd=config.workspace,
        env=_tool_env(config),
        text=True,
        capture_output=True,
        timeout=config.tool_timeout_seconds,
        check=False,
    )
    metadata = _read_json_object(config.workspace / "metadata.json")
    forbidden = _extract_forbidden_imports(metadata)
    forbidden_hits = _scan_forbidden_imports(config.submission_dir / "featurelifted", forbidden)
    public_tests = _run_public_tests_command(config)
    status = (
        "success"
        if import_probe.returncode == 0
        and not forbidden_hits
        and public_tests["status"] in {"success", "unavailable"}
        else "failed"
    )
    output = {
        "import_returncode": import_probe.returncode,
        "import_stdout": import_probe.stdout,
        "import_stderr": import_probe.stderr,
        "forbidden_import_hits": forbidden_hits,
        "public_tests": public_tests,
    }
    _record_repo_graph_tool_evidence(
        config,
        kind="verification_result",
        probe_type="final_verification",
        evidence_class="api_probe",
        status="supports" if status == "success" else "failed",
        input_summary="import probe, forbidden import scan, and public tests",
        result_summary=(
            f"import={import_probe.returncode}; forbidden={len(forbidden_hits)}; "
            f"public={public_tests['status']}"
        ),
        command="featurelift-agent final_check",
    )
    guard = _repo_graph_native_stopping_guard(config, sync=False)
    if status == "success" and guard is not None and not guard.get("ready", False):
        status = "failed"
        output["repo_graph_stopping_guard"] = guard
    return _tool_observation(
        phase=phase,
        action_index=action_index,
        action_type="final_check",
        target=_action_text_field(action, "target") or "featurelifted import and forbidden imports",
        reason=reason,
        status=status,
        summary=(
            f"import_returncode={import_probe.returncode}; "
            f"forbidden_import_hits={len(forbidden_hits)}; "
            f"public_tests={public_tests['status']}"
        ),
        output=json.dumps(output, indent=2, sort_keys=True),
        returncode=import_probe.returncode,
    )


def _repo_graph_evidence_enabled(config: FeatureLiftAgentConfig) -> bool:
    return (
        config.agent_output_dir / "state" / "repo_graph" / "semantic_claims.jsonl"
    ).is_file()


def _sync_repo_graph_after_mutation(config: FeatureLiftAgentConfig) -> dict[str, Any] | None:
    if not _repo_graph_evidence_enabled(config):
        return None
    from .repo_graph.submission import sync_submission

    return sync_submission(
        config.agent_output_dir / "state" / "repo_graph",
        config.submission_dir,
    )


def _record_repo_graph_tool_evidence(
    config: FeatureLiftAgentConfig,
    *,
    kind: str,
    probe_type: str,
    evidence_class: str,
    status: str,
    input_summary: str,
    result_summary: str,
    command: str,
) -> dict[str, Any] | None:
    if not _repo_graph_evidence_enabled(config):
        return None
    from .repo_graph.ledger import RepoGraphLedger

    return RepoGraphLedger(
        config.agent_output_dir / "state" / "repo_graph"
    ).record_evidence(
        kind=kind,
        probe_type=probe_type,
        evidence_class=evidence_class,
        status=status,
        input_summary=input_summary,
        result_summary=result_summary,
        command=command,
    )


def _repo_graph_native_stopping_guard(
    config: FeatureLiftAgentConfig,
    *,
    sync: bool = True,
) -> dict[str, Any] | None:
    if not _repo_graph_evidence_enabled(config):
        return None
    from .repo_graph.ledger import RepoGraphLedger

    if sync:
        _sync_repo_graph_after_mutation(config)
    guard = RepoGraphLedger(
        config.agent_output_dir / "state" / "repo_graph"
    ).stopping_guard()
    (config.agent_output_dir / "state" / "repo_graph" / "stopping_guard.json").write_text(
        json.dumps(guard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return guard


def _run_public_tests_command(config: FeatureLiftAgentConfig) -> dict[str, Any]:
    public_dir = config.workspace / "public_tests"
    if not public_dir.is_dir():
        return {
            "command": [],
            "status": "unavailable",
            "summary": (
                "benchmark evaluator tests are not mounted; inspect upstream tests under "
                "repo/ or run agent-authored tests"
            ),
            "output": "",
            "returncode": None,
        }
    python = _ensure_agent_tool_python(config)
    command = [str(python), "-m", "pytest", "-q", "public_tests"]
    try:
        completed = subprocess.run(
            command,
            cwd=config.workspace,
            env=_tool_env(config),
            text=True,
            capture_output=True,
            timeout=config.tool_timeout_seconds,
            check=False,
        )
        output = _bounded_text(
            (completed.stdout or "") + (completed.stderr or ""),
            config.max_observation_chars,
        )
        return {
            "command": command,
            "status": "success" if completed.returncode == 0 else "failed",
            "summary": f"pytest exited {completed.returncode}",
            "output": output,
            "returncode": completed.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        output = _bounded_text(stdout + stderr, config.max_observation_chars)
        return {
            "command": command,
            "status": "timeout",
            "summary": f"pytest timed out after {config.tool_timeout_seconds}s",
            "output": output,
            "returncode": None,
        }


def _tool_observation(
    *,
    phase: str,
    action_index: int,
    action_type: str,
    target: str,
    reason: str,
    status: str,
    summary: str,
    output: str = "",
    truncated: bool = False,
    returncode: int | None = None,
) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "schema_version": "featureliftbench.tool_observation.v1",
        "phase": phase,
        "action_index": action_index,
        "action_type": action_type,
        "target": target,
        "reason": reason,
        "status": status,
        "summary": summary,
        "truncated": truncated,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    if output:
        observation["output"] = output
    if returncode is not None:
        observation["returncode"] = returncode
    return observation


def _append_tool_observation(state_dir: Path, observation: dict[str, Any]) -> None:
    with (state_dir / "tool_observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(observation, sort_keys=True) + "\n")

    log_path = _observation_log_path(state_dir, observation)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n\n"
            f"## Tool Observation: {observation.get('phase')} #{observation.get('action_index')} "
            f"{observation.get('action_type')}\n\n"
            f"- Target: `{observation.get('target', '')}`\n"
            f"- Status: `{observation.get('status', '')}`\n"
            f"- Summary: {observation.get('summary', '')}\n"
        )
        output = observation.get("output")
        if isinstance(output, str) and output:
            handle.write("\n```text\n")
            handle.write(output)
            if not output.endswith("\n"):
                handle.write("\n")
            handle.write("```\n")


def _observation_log_path(state_dir: Path, observation: dict[str, Any]) -> Path:
    action_type = observation.get("action_type")
    if action_type == "run_public_tests":
        return state_dir / "test_log.md"
    if action_type == "prune_submission":
        return state_dir / "prune_log.md"
    if action_type == "final_check":
        return state_dir / "final_checklist.md"
    return state_dir / "extraction_log.md"


def _action_text_field(action: dict[str, Any], *names: str) -> str:
    for name in names:
        value = action.get(name)
        if isinstance(value, str):
            return value.strip()
    return ""


def _resolve_readable_workspace_path(config: FeatureLiftAgentConfig, raw_path: str) -> Path:
    if not raw_path:
        raise FeatureLiftAgentError("path is required")
    root = config.workspace.resolve()
    candidate = Path(raw_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not candidate.is_absolute() and not resolved.exists():
        repo_relative = (root / "repo" / candidate).resolve()
        if repo_relative.exists():
            resolved = repo_relative
    if not _is_relative_to(resolved, root):
        raise FeatureLiftAgentError(f"path escapes workspace: {raw_path}")
    rel_parts = resolved.relative_to(root).parts
    if any(part in {"hidden_tests", "evaluation"} for part in rel_parts):
        raise FeatureLiftAgentError(f"path is outside the agent-visible task boundary: {raw_path}")
    return resolved


def _count_files(path: Path) -> int:
    if path.is_file():
        return 1
    if not path.is_dir():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _resolve_submission_path(config: FeatureLiftAgentConfig, raw_path: str) -> Path:
    if not raw_path:
        raise FeatureLiftAgentError("submission path is required")
    workspace_root = config.workspace.resolve()
    submission_root = config.submission_dir.resolve()
    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    elif candidate.parts and candidate.parts[0] == "submission":
        resolved = (workspace_root / candidate).resolve()
    else:
        resolved = (submission_root / candidate).resolve()
    if not _is_relative_to(resolved, submission_root):
        raise FeatureLiftAgentError(f"path escapes submission directory: {raw_path}")
    return resolved


def _read_bounded_file(path: Path, limit: int) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return _bounded_text(text, limit), len(text) > limit


def _bounded_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]\n"


def _workspace_relative(config: FeatureLiftAgentConfig, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.workspace.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _tool_env(config: FeatureLiftAgentConfig) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    paths = [str(config.submission_dir)]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_agent_tool_python(config: FeatureLiftAgentConfig) -> Path:
    workspace_key = str(config.workspace.resolve())
    venv_dir = config.workspace / AGENT_TOOL_VENV_DIRNAME
    python_path = _venv_python_path(venv_dir)
    if workspace_key in _AGENT_TOOL_VENV_READY and python_path.is_file():
        return python_path

    if not python_path.is_file():
        completed = subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
            cwd=config.workspace,
            text=True,
            capture_output=True,
            timeout=config.tool_timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise FeatureLiftAgentError(
                "failed to create agent tool venv: "
                + (completed.stderr or completed.stdout or "unknown error").strip()
            )

    metadata_path = config.workspace / "metadata.json"
    if metadata_path.is_file():
        metadata = _read_json_object(metadata_path)
        install_result = install_dependency_lock(
            venv_python=python_path,
            task_path=config.workspace,
            metadata=metadata,
            cwd=config.workspace,
            env=_tool_env(config),
            timeout_seconds=config.tool_timeout_seconds,
        )
        if not install_result.skipped and not install_result.passed:
            raise FeatureLiftAgentError(
                "failed to install task dependencies for agent tools: "
                + (install_result.reason or install_result.stderr or "unknown error").strip()
            )

    _AGENT_TOOL_VENV_READY.add(workspace_key)
    return python_path


def _extract_forbidden_imports(metadata: dict[str, Any]) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []
    forbidden = environment.get("forbidden_imports")
    if not isinstance(forbidden, list):
        return []
    return [item for item in forbidden if isinstance(item, str) and item]


def _scan_forbidden_imports(package_dir: Path, forbidden: list[str]) -> list[dict[str, Any]]:
    if not forbidden or not package_dir.is_dir():
        return []
    hits: list[dict[str, Any]] = []
    for path in sorted(package_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            for name in forbidden:
                if (
                    stripped == f"import {name}"
                    or stripped.startswith(f"import {name}.")
                    or stripped.startswith(f"from {name} ")
                    or stripped.startswith(f"from {name}.")
                ):
                    hits.append(
                        {
                            "path": path.as_posix(),
                            "line": lineno,
                            "import": name,
                            "source": stripped,
                        }
                    )
    return hits


def _prune_submission_transients(submission_dir: Path) -> list[str]:
    root = submission_dir.resolve()
    if not root.is_dir():
        return []
    removable_dir_names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    removable_suffixes = {".pyc", ".pyo"}
    removed: list[str] = []
    for path in sorted(root.rglob("*"), reverse=True):
        resolved = path.resolve()
        if not _is_relative_to(resolved, root):
            continue
        should_remove = (
            path.is_dir()
            and path.name in removable_dir_names
        ) or (
            path.is_file()
            and path.suffix in removable_suffixes
        )
        if not should_remove:
            continue
        try:
            relative = resolved.relative_to(root).as_posix()
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(relative)
        except OSError:
            continue
    return removed


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _extract_json_object_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    candidates = [stripped]
    if "```json" in stripped:
        after = stripped.split("```json", 1)[1]
        candidates.insert(0, after.split("```", 1)[0].strip())
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _write_state_files(config: FeatureLiftAgentConfig, state_dir: Path, task_text: str) -> None:
    metadata = _read_json_object(config.workspace / "metadata.json")
    repo_summary = _summarize_repo(config.workspace / "repo")
    source_entrypoints = _extract_source_entrypoints(metadata)
    (state_dir / "task_brief.md").write_text(
        "# Task Brief\n\n"
        f"- Workspace: `{config.workspace}`\n"
        f"- Submission dir: `{config.submission_dir}`\n"
        f"- Model: `{config.model or 'unspecified'}`\n"
        f"- Runtime: `{config.runtime}`\n"
        f"- Task id: `{metadata.get('task_id', '')}`\n"
        f"- Language: `{metadata.get('language', 'python')}`\n"
        f"- Task file chars: {len(task_text)}\n",
        encoding="utf-8",
    )
    _write_repo_map(state_dir / "repo_map.md", repo_summary)
    (state_dir / "action_schema.json").write_text(
        json.dumps(
            _action_schema(
                repo_graph_enabled=(state_dir / "repo_graph" / "base" / "manifest.json").is_file(),
                repo_graph_evidence_enabled=(
                    state_dir / "repo_graph" / "semantic_claims.jsonl"
                ).is_file(),
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    if source_entrypoints is not None:
        (state_dir / "source_entrypoints.json").write_text(
            json.dumps(source_entrypoints, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    (state_dir / "closure_plan.md").write_text(
        "# Closure Plan\n\n"
        "Status: not started.\n\n"
        "Planned phases: repo map, dependency manifest, extraction, public tests, "
        "hidden-boundary check, footprint pruning, final audit.\n",
        encoding="utf-8",
    )
    (state_dir / "extraction_plan.md").write_text(
        "# Extraction Plan\n\nPending.\n",
        encoding="utf-8",
    )
    dependency_manifest = {
        "schema_version": "featureliftbench.dependency_manifest.v1",
        "runtime_files": [],
        "resource_files": [],
        "third_party_dependencies": _extract_declared_dependencies(metadata),
        "excluded_subsystems": [],
        "risk_points": ["controller scaffold only; no model runtime attached yet"],
    }
    if source_entrypoints is not None:
        dependency_manifest["source_entrypoints"] = source_entrypoints["entrypoints"]
    (state_dir / "dependency_manifest.json").write_text(
        json.dumps(dependency_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for name in (
        "extraction_log.md",
        "test_log.md",
        "hidden_boundary_check.md",
        "prune_log.md",
        "final_checklist.md",
    ):
        (state_dir / name).write_text(f"# {name.removesuffix('.md').replace('_', ' ').title()}\n\nPending.\n", encoding="utf-8")


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _action_schema(
    *,
    repo_graph_enabled: bool = False,
    repo_graph_evidence_enabled: bool = False,
) -> dict[str, Any]:
    action_types: dict[str, Any] = {
        "inspect_file": {
            "description": "Read or inspect a workspace file before deciding closure.",
            "required_fields": ["target", "reason"],
        },
        "copy_file": {
            "description": "Copy a source file into submission/featurelifted or package resources.",
            "required_fields": ["target", "reason"],
            "optional_fields": ["source", "destination"],
        },
        "write_file": {
            "description": "Create or edit a file under submission/.",
            "required_fields": ["target", "reason"],
            "optional_fields": ["content"],
        },
        "run_public_tests": {
            "description": "Run public tests or output API probes available in the workspace.",
            "required_fields": ["target", "reason"],
        },
        "prune_submission": {
            "description": "Remove known transient cache/build files from submission/ only.",
            "required_fields": ["target", "reason"],
        },
        "final_check": {
            "description": "Run final pre-submit audit checks.",
            "required_fields": ["target", "reason"],
        },
    }
    if repo_graph_enabled:
        action_types["repo_graph_query"] = {
            "description": "Run one bounded query against the run-local advisory repository graph.",
            "required_fields": ["command", "reason"],
            "optional_fields": ["target", "query", "node", "source", "destination", "entrypoints"],
            "commands": [
                "bootstrap",
                "search",
                "inspect",
                "paths",
                "closure",
                "risks",
                "self-check",
                "sync-submission",
                "compare",
                "detectors",
                "freshness",
                "stopping-check",
                "claim-list",
                "evidence-list",
            ],
        }
    if repo_graph_evidence_enabled:
        action_types["repo_graph_claim"] = {
            "description": "Add a closure claim or request a status transition guarded by recorded evidence.",
            "required_fields": ["operation", "reason"],
            "optional_fields": [
                "subject",
                "predicate",
                "object",
                "classification",
                "confidence",
                "claim_id",
                "status",
                "evidence_ids",
            ],
            "operations": ["add", "update"],
        }
    return {
        "schema_version": "featureliftbench.agent_action_schema.v1",
        "action_types": action_types,
    }


def _repo_graph_phase_context(state_dir: Path) -> str:
    graph_dir = state_dir / "repo_graph"
    bootstrap = graph_dir / "bootstrap.md"
    if not bootstrap.is_file():
        return ""
    chunks = ["\n## repo_graph/bootstrap.md\n", _read_text(bootstrap), "\n"]
    for name in ("task_overlay.json", "closure_overlay.json"):
        path = graph_dir / name
        if path.is_file():
            chunks.extend([f"\n## repo_graph/{name}\n", _read_text(path), "\n"])
    return "".join(chunks)


def _source_hint_phase_context(state_dir: Path) -> str:
    path = state_dir / "source_entrypoints.json"
    if not path.is_file():
        return ""
    return f"## source_entrypoints.json\n{_read_text(path)}\n\n"


def _extract_source_entrypoints(metadata: dict[str, Any]) -> dict[str, Any] | None:
    feature = metadata.get("feature") if isinstance(metadata.get("feature"), dict) else {}
    output = metadata.get("output") if isinstance(metadata.get("output"), dict) else {}
    if "source_entrypoints" not in feature:
        return None
    raw_entrypoints = feature.get("source_entrypoints")
    entrypoints = [
        str(item)
        for item in raw_entrypoints
        if isinstance(item, str) and item
    ] if isinstance(raw_entrypoints, list) else []
    return {
        "schema_version": "featureliftbench.source_entrypoints.v1",
        "task_id": metadata.get("task_id", ""),
        "feature_name": feature.get("name", ""),
        "entrypoints": entrypoints,
        "output": {
            "package": output.get("package", ""),
            "import": output.get("import", ""),
            "callable": output.get("callable", ""),
            "module": output.get("module", ""),
            "symbols": output.get("symbols", []),
        },
    }


def _extract_declared_dependencies(metadata: dict[str, Any]) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []
    dependencies = environment.get("dependencies")
    if not isinstance(dependencies, list):
        return []
    return [str(item) for item in dependencies if isinstance(item, str) and item]


def _summarize_repo(repo_dir: Path) -> dict[str, Any]:
    if not repo_dir.is_dir():
        return {
            "exists": False,
            "file_count": 0,
            "directory_count": 0,
            "top_level_entries": [],
            "extension_counts": {},
            "sample_files": [],
        }

    file_count = 0
    directory_count = 0
    extension_counts: collections.Counter[str] = collections.Counter()
    sample_files: list[str] = []
    max_samples = 200

    for path in sorted(repo_dir.rglob("*")):
        if _is_ignored_repo_path(path):
            continue
        if path.is_dir():
            directory_count += 1
            continue
        if not path.is_file():
            continue
        file_count += 1
        suffix = path.suffix.lower() or "<none>"
        extension_counts[suffix] += 1
        if len(sample_files) < max_samples:
            sample_files.append(path.relative_to(repo_dir).as_posix())

    top_level_entries = [
        path.name + ("/" if path.is_dir() else "")
        for path in sorted(repo_dir.iterdir())
        if not _is_ignored_repo_path(path)
    ][:100]
    return {
        "exists": True,
        "file_count": file_count,
        "directory_count": directory_count,
        "top_level_entries": top_level_entries,
        "extension_counts": dict(sorted(extension_counts.items())),
        "sample_files": sample_files,
        "sample_truncated": file_count > len(sample_files),
    }


def _is_ignored_repo_path(path: Path) -> bool:
    ignored_names = {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
        ".tox",
        ".venv",
        "venv",
    }
    return any(part in ignored_names for part in path.parts)


def _write_repo_map(path: Path, summary: dict[str, Any]) -> None:
    extension_counts = summary.get("extension_counts")
    extension_lines = []
    if isinstance(extension_counts, dict):
        extension_lines = [
            f"- `{extension}`: {count}"
            for extension, count in extension_counts.items()
        ]
    sample_files = summary.get("sample_files")
    sample_lines = []
    if isinstance(sample_files, list):
        sample_lines = [f"- `{item}`" for item in sample_files[:200] if isinstance(item, str)]
    top_level = summary.get("top_level_entries")
    top_level_lines = []
    if isinstance(top_level, list):
        top_level_lines = [f"- `{item}`" for item in top_level if isinstance(item, str)]

    path.write_text(
        "# Repository Map\n\n"
        f"- Exists: {summary.get('exists', False)}\n"
        f"- Files: {summary.get('file_count', 0)}\n"
        f"- Directories: {summary.get('directory_count', 0)}\n"
        f"- Sample truncated: {summary.get('sample_truncated', False)}\n\n"
        "## Top-Level Entries\n\n"
        + ("\n".join(top_level_lines) if top_level_lines else "- None")
        + "\n\n## Extension Counts\n\n"
        + ("\n".join(extension_lines) if extension_lines else "- None")
        + "\n\n## Sample Files\n\n"
        + ("\n".join(sample_lines) if sample_lines else "- None")
        + "\n",
        encoding="utf-8",
    )


def _create_submission_scaffold(submission_dir: Path) -> None:
    package_dir = submission_dir / "featurelifted"
    package_dir.mkdir(parents=True, exist_ok=True)
    (submission_dir / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        'name = "featurelifted"\n'
        'version = "0.0.0"\n',
        encoding="utf-8",
    )
    init_path = package_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '"""FeatureLiftAgent scaffold package.\n\n'
            "The extraction runtime has not populated this package yet.\n"
            '"""\n',
            encoding="utf-8",
        )


def _write_usage(
    config: FeatureLiftAgentConfig,
    *,
    available: bool,
    context_violation: bool,
    audit_records: list[dict[str, Any]],
    usage_totals: dict[str, int],
    exit_status: str,
    tool_observations: list[dict[str, Any]] | None = None,
) -> None:
    max_prompt = max(
        (
            value
            for record in audit_records
            if isinstance((value := record.get("prompt_tokens")), int)
        ),
        default=0,
    )
    max_total = max(
        (
            value
            for record in audit_records
            if isinstance((value := record.get("total_tokens")), int)
        ),
        default=max_prompt,
    )
    model_call_records = [
        record for record in audit_records if record.get("is_model_call") is True
    ]
    usage_unverified = not model_call_records or any(
        record.get("token_source") != "provider_usage" for record in model_call_records
    )
    payload: dict[str, Any] = {
        "schema_version": USAGE_SCHEMA_VERSION,
        "agent_name": "featurelift-agent",
        "model": config.model,
        "available": available,
        "context_audit": {
            "available": True,
            "context_window_tokens": config.context_window_tokens,
            "reserved_output_tokens": config.reserved_output_tokens,
            "max_allowed_prompt_tokens": config.max_allowed_prompt_tokens,
            "history_policy": "stateful_bounded",
            "over_context_behavior": "fail_before_call",
            "token_source": "provider_usage" if not usage_unverified else "estimated_chars_div4",
            "max_prompt_tokens_per_call": max_prompt,
            "max_total_tokens_per_call": max_total,
            "context_violation": context_violation,
            "usage_unverified": usage_unverified,
            "runtime": config.runtime,
        },
        "assistant_steps": usage_totals.get("assistant_steps", 0),
        "total_messages": usage_totals.get("total_messages", 0),
        "api_calls": usage_totals.get("api_calls", 0),
        "prompt_tokens": usage_totals.get("prompt_tokens", 0),
        "completion_tokens": usage_totals.get("completion_tokens", 0),
        "total_tokens": usage_totals.get("total_tokens", 0),
        "tool_summary": _summarize_tool_observations(
            tool_observations or [],
            actions_enabled=config.execute_actions,
        ),
        "exit_status": exit_status,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (config.agent_output_dir / "usage.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_context_audit(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _completed_exit_status(
    config: FeatureLiftAgentConfig,
    tool_observations: list[dict[str, Any]],
) -> str:
    if not config.enable_llm:
        return "scaffold_initialized"
    if not config.execute_actions:
        return "llm_phases_complete"
    summary = _summarize_tool_observations(tool_observations, actions_enabled=True)
    has_historical_failure = any(
        summary[key]
        for key in ("failed_actions", "blocked_actions", "timeout_actions", "error_actions")
    )
    if summary.get("final_check_status") == "success":
        return "actions_complete_with_repairs" if has_historical_failure else "actions_complete"
    if summary["failed_actions"] or summary["blocked_actions"] or summary["timeout_actions"] or summary["error_actions"]:
        return "actions_failed"
    if summary.get("final_check_status") not in {"", "success"}:
        return "actions_failed"
    return "actions_complete"


def _summarize_tool_observations(
    observations: list[dict[str, Any]],
    *,
    actions_enabled: bool,
) -> dict[str, Any]:
    counts: collections.Counter[str] = collections.Counter()
    action_types: collections.Counter[str] = collections.Counter()
    final_check_status = ""
    public_tests_status = ""
    for observation in observations:
        status = observation.get("status")
        if isinstance(status, str):
            counts[status] += 1
        action_type = observation.get("action_type")
        if isinstance(action_type, str):
            action_types[action_type] += 1
            if action_type == "final_check" and isinstance(status, str):
                final_check_status = status
            if action_type == "run_public_tests" and isinstance(status, str):
                public_tests_status = status
    return {
        "available": True,
        "actions_enabled": actions_enabled,
        "total_actions": len(observations),
        "success_actions": counts["success"],
        "failed_actions": counts["failed"],
        "blocked_actions": counts["blocked"],
        "timeout_actions": counts["timeout"],
        "error_actions": counts["error"],
        "action_types": dict(sorted(action_types.items())),
        "final_check_status": final_check_status,
        "public_tests_status": public_tests_status,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _cheap_token_estimate(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _parse_llm_phases(value: str) -> tuple[str, ...]:
    phases = tuple(part.strip() for part in value.split(",") if part.strip())
    if not phases:
        raise ValueError("--llm-phases must include at least one phase")
    unknown = [phase for phase in phases if phase not in VALID_LLM_PHASES]
    if unknown:
        allowed = ", ".join(VALID_LLM_PHASES)
        raise ValueError(f"unknown --llm-phases value(s): {', '.join(unknown)}; allowed: {allowed}")
    duplicates = sorted({phase for phase in phases if phases.count(phase) > 1})
    if duplicates:
        raise ValueError(f"duplicate --llm-phases value(s): {', '.join(duplicates)}")
    return phases


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else None


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
