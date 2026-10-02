"""Local experiment configuration (flb.local.toml) loading and runtime policy."""

from __future__ import annotations

import hashlib
import os
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .agent_adapters import AgentRunConfig
from .agent_config import (
    DEFAULT_OPENHANDS_COMMAND,
    LoadedAgentConfig,
    _first_non_empty,
    _first_non_empty_with_source,
    _has_env_file_conflict,
    _is_openhands_agent,
    _merge_extra_args,
    _positive_int_value,
    _read_env_file,
    _resolve_openhands_command,
    _set_api_base_env,
    _set_secret_env,
    _string_value,
    _truthy,
    load_agent_run_config,
)
from .llm_env import apply_openhands_llm_env
from .paths import (
    DEFAULT_AGENT_CONFIG,
    DEFAULT_LOCAL_CONFIG,
    DEFAULT_LOCAL_CONFIG_EXAMPLE,
    EXPERIMENTS_SMOKE_DIR,
    REPO_ROOT,
    SANITY_TASKS_DIR,
    TASKS_DIR,
    resolve_openhands_run_dir,
)

SUITE_NAMES = frozenset({"sanity", "smoke", "pilot5", "main", "custom"})
PILOT5_BATCH_TASK_IDS = (
    "arrow__parse_format_core__001",
    "bleach__sanitize_core__001",
)
SMOKE_FIRST_TASK = SANITY_TASKS_DIR / "iniconfig__parse_config__001"
DEFAULT_RESERVED_OUTPUT_TOKENS = 8192
DEFAULT_API_KEY_ENV = "FEATURELIFTBENCH_API_KEY"


@dataclass(frozen=True)
class SuitePhase:
    """One run-agent pass within a suite preset."""

    name: str
    task_root: Path
    output_subdir: str
    task_ids: tuple[str, ...] = ()
    retry_rate_limit: int | None = None


@dataclass(frozen=True)
class SuitePreset:
    """Resolved suite execution plan."""

    name: str
    phases: tuple[SuitePhase, ...]
    strict_preflight: bool = False
    merge_pilot: bool = False
    run_smoke_check: bool = False
    default_max_steps: int = 120
    default_retry_rate_limit: int = 1
    run_analysis: bool = True
    run_infra_summary: bool = False
    run_entanglement_report: bool = False


@dataclass(frozen=True)
class LocalLlmConfig:
    model: str
    base_url: str
    api_key_env: str
    native_tool_calling: bool | None
    context_window_tokens: int | None
    reserved_output_tokens: int
    profile: str | None


@dataclass(frozen=True)
class LocalAgentConfig:
    kind: str
    max_steps: int
    timeout_seconds: int


@dataclass(frozen=True)
class LocalRunConfig:
    suite: str
    workers: int
    output_dir: str
    agent_docker: bool
    eval_docker: bool
    extra_agent_passes: int
    retry_rate_limit: int
    task_cooldown_seconds: float
    custom_task_root: str
    custom_task_ids: tuple[str, ...]


@dataclass(frozen=True)
class LocalConfig:
    llm: LocalLlmConfig
    agent: LocalAgentConfig
    run: LocalRunConfig
    config_path: Path
    env_file: Path


@dataclass(frozen=True)
class RuntimePolicy:
    """Environment variables to apply before preflight / run-agent."""

    env: dict[str, str]
    agent_docker_network: str | None


def default_local_config_path() -> Path:
    if DEFAULT_LOCAL_CONFIG.is_file():
        return DEFAULT_LOCAL_CONFIG
    return DEFAULT_LOCAL_CONFIG


def load_local_config(path: str | Path | None = None) -> LocalConfig:
    config_path = Path(path).resolve() if path else default_local_config_path()
    if not config_path.is_file():
        hint = DEFAULT_LOCAL_CONFIG_EXAMPLE
        raise ValueError(
            f"local config not found: {config_path}; "
            f"copy {hint} to {DEFAULT_LOCAL_CONFIG} and edit"
        )

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid local config TOML: {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"local config must be a TOML table: {config_path}")

    llm_table = data.get("llm")
    agent_table = data.get("agent")
    run_table = data.get("run")
    if not isinstance(llm_table, dict):
        raise ValueError("[llm] table is required in flb.local.toml")
    if not isinstance(agent_table, dict):
        raise ValueError("[agent] table is required in flb.local.toml")
    if not isinstance(run_table, dict):
        raise ValueError("[run] table is required in flb.local.toml")

    model = _string_value(llm_table.get("model"))
    base_url = _first_non_empty(
        _string_value(llm_table.get("base_url")),
        _string_value(llm_table.get("api_base")),
    )
    if not model:
        raise ValueError("[llm].model is required")
    if not base_url:
        raise ValueError("[llm].base_url is required")

    suite = _string_value(run_table.get("suite")) or "sanity"
    if suite not in SUITE_NAMES:
        raise ValueError(f"[run].suite must be one of: {', '.join(sorted(SUITE_NAMES))}")

    custom_table = run_table.get("custom")
    custom_task_root = "benchmark/tasks"
    custom_task_ids: tuple[str, ...] = ()
    if isinstance(custom_table, dict):
        custom_task_root = _string_value(custom_table.get("task_root")) or custom_task_root
        raw_ids = custom_table.get("task_ids")
        if isinstance(raw_ids, list):
            custom_task_ids = tuple(str(item) for item in raw_ids if str(item).strip())

    native_tool_calling = llm_table.get("native_tool_calling")
    if native_tool_calling is not None and not isinstance(native_tool_calling, bool):
        native_tool_calling = _truthy(native_tool_calling)

    if run_table.get("smoke_first") is not None:
        print(
            "flb.local.toml: [run].smoke_first is deprecated and ignored; "
            "run smoke and main as separate commands: "
            "featureliftbench run --suite smoke, then --suite main",
            file=sys.stderr,
        )

    return LocalConfig(
        llm=LocalLlmConfig(
            model=normalize_local_vllm_model(model, base_url),
            base_url=base_url,
            api_key_env=_string_value(llm_table.get("api_key_env")) or DEFAULT_API_KEY_ENV,
            native_tool_calling=native_tool_calling if isinstance(native_tool_calling, bool) else None,
            context_window_tokens=_positive_int_value(llm_table.get("context_window_tokens")),
            reserved_output_tokens=(
                _positive_int_value(llm_table.get("reserved_output_tokens"))
                or DEFAULT_RESERVED_OUTPUT_TOKENS
            ),
            profile=_string_value(llm_table.get("profile")) or None,
        ),
        agent=LocalAgentConfig(
            kind=_string_value(agent_table.get("kind")) or "openhands-agent",
            max_steps=_positive_int_value(agent_table.get("max_steps")) or 120,
            timeout_seconds=_positive_int_value(agent_table.get("timeout_seconds")) or 3600,
        ),
        run=LocalRunConfig(
            suite=suite,
            workers=max(1, _positive_int_value(run_table.get("workers")) or 1),
            output_dir=_string_value(run_table.get("output_dir")),
            agent_docker=_config_bool(run_table.get("agent_docker"), default=True),
            eval_docker=_config_bool(run_table.get("eval_docker"), default=True),
            extra_agent_passes=max(0, _positive_int_value(run_table.get("extra_agent_passes")) or 0),
            retry_rate_limit=max(1, _positive_int_value(run_table.get("retry_rate_limit")) or 5),
            task_cooldown_seconds=_float_value(run_table.get("task_cooldown_seconds")),
            custom_task_root=custom_task_root,
            custom_task_ids=custom_task_ids,
        ),
        config_path=config_path,
        env_file=REPO_ROOT / ".env",
    )


def normalize_local_vllm_model(model: str, base_url: str) -> str:
    """Add openai/ prefix for local vLLM when the user supplies a bare served name."""
    if not model or "/" in model:
        return model
    if is_local_api_base(base_url):
        return f"openai/{model}"
    return model


def is_local_api_base(api_base: str) -> bool:
    try:
        parsed = urlsplit(api_base)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def resolve_suite_preset(local_config: LocalConfig) -> SuitePreset:
    suite = local_config.run.suite

    if suite == "sanity":
        return SuitePreset(
            name="sanity",
            phases=(
                SuitePhase(
                    name="sanity",
                    task_root=SANITY_TASKS_DIR,
                    output_subdir=".",
                ),
            ),
            default_max_steps=120,
            default_retry_rate_limit=1,
            run_entanglement_report=True,
        )

    if suite == "pilot5":
        return SuitePreset(
            name="pilot5",
            phases=(
                SuitePhase(
                    name="sanity3",
                    task_root=SANITY_TASKS_DIR,
                    output_subdir="sanity3",
                    retry_rate_limit=1,
                ),
                SuitePhase(
                    name="batch2",
                    task_root=TASKS_DIR,
                    output_subdir="batch2",
                    task_ids=PILOT5_BATCH_TASK_IDS,
                    retry_rate_limit=1,
                ),
            ),
            default_max_steps=120,
            default_retry_rate_limit=1,
            merge_pilot=True,
        )

    if suite == "smoke":
        return SuitePreset(
            name="smoke",
            phases=(
                SuitePhase(
                    name="smoke",
                    task_root=SMOKE_FIRST_TASK,
                    output_subdir=".",
                ),
            ),
            default_max_steps=120,
            default_retry_rate_limit=1,
            run_smoke_check=True,
        )

    if suite == "main":
        return SuitePreset(
            name="main",
            phases=(
                SuitePhase(
                    name="main",
                    task_root=TASKS_DIR,
                    output_subdir=".",
                ),
            ),
            strict_preflight=True,
            default_max_steps=180,
            default_retry_rate_limit=5,
            run_infra_summary=True,
            run_entanglement_report=True,
        )

    custom_root = (REPO_ROOT / local_config.run.custom_task_root).resolve()
    return SuitePreset(
        name="custom",
        phases=(
            SuitePhase(
                name="custom",
                task_root=custom_root,
                output_subdir=".",
                task_ids=local_config.run.custom_task_ids,
            ),
        ),
        default_max_steps=local_config.agent.max_steps,
        default_retry_rate_limit=local_config.run.retry_rate_limit,
    )


def resolve_runtime_policy(local_config: LocalConfig) -> RuntimePolicy:
    env_values = _read_env_file(local_config.env_file)
    api_key_env = local_config.llm.api_key_env
    api_key, _ = _first_non_empty_with_source(
        ("environment", os.environ.get(api_key_env)),
        (".env", env_values.get(api_key_env)),
    )
    api_base = local_config.llm.base_url

    env: dict[str, str] = {}
    api_base_env = _infer_api_base_env(api_key_env)
    if api_key:
        env[api_key_env] = api_key
        _set_secret_env(env, api_key)
    elif api_key_env in env_values:
        env[api_key_env] = env_values[api_key_env]
    if api_base:
        env[api_base_env] = api_base
        _set_api_base_env(env, api_base)

    model = local_config.llm.model
    if model:
        env["FEATURELIFTBENCH_MODEL"] = model

    max_steps = local_config.agent.max_steps
    env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"] = str(max_steps)

    if local_config.run.agent_docker:
        env["FEATURELIFTBENCH_AGENT_DOCKER"] = "1"
    if local_config.run.eval_docker:
        env["FEATURELIFTBENCH_EVAL_DOCKER"] = "1"

    cooldown = local_config.run.task_cooldown_seconds
    if cooldown > 0:
        env["FEATURELIFTBENCH_SUITE_TASK_COOLDOWN_SECONDS"] = str(cooldown)

    if _is_openhands_agent(local_config.agent.kind):
        env = apply_openhands_llm_env(env)

    agent_docker_network: str | None = None
    if local_config.run.agent_docker and is_local_api_base(api_base):
        agent_docker_network = "host"
        env["FEATURELIFTBENCH_AGENT_DOCKER_NETWORK"] = "host"

    return RuntimePolicy(env=env, agent_docker_network=agent_docker_network)


def load_local_agent_config(local_config: LocalConfig) -> LoadedAgentConfig:
    """Build a LoadedAgentConfig from flb.local.toml, optionally falling back to agents.toml profile."""
    if local_config.llm.profile:
        return load_agent_run_config(
            base_config=AgentRunConfig(
                agent=local_config.agent.kind,
                timeout_seconds=local_config.agent.timeout_seconds,
            ),
            config_path=DEFAULT_AGENT_CONFIG,
            profile_name=local_config.llm.profile,
            env_file=local_config.env_file,
        )

    env_values = _read_env_file(local_config.env_file)
    api_key_env = local_config.llm.api_key_env
    api_base_env = _infer_api_base_env(api_key_env)
    api_key, api_key_source = _first_non_empty_with_source(
        ("environment", os.environ.get(api_key_env)),
        (".env", env_values.get(api_key_env)),
    )
    api_base = local_config.llm.base_url
    api_key_env_conflict = _has_env_file_conflict(api_key_env, env_values)
    api_base_env_conflict = _has_env_file_conflict(api_base_env, env_values)

    profile: dict[str, Any] = {
        "model": local_config.llm.model,
        "api_key_env": api_key_env,
        "api_base_env": api_base_env,
        "openhands_command": DEFAULT_OPENHANDS_COMMAND,
        "cost_limit": "0",
        "call_limit": "0",
    }
    if local_config.llm.native_tool_calling is not None:
        profile["native_tool_calling"] = local_config.llm.native_tool_calling
    if local_config.llm.context_window_tokens is not None:
        profile["context_window_tokens"] = local_config.llm.context_window_tokens
    profile["reserved_output_tokens"] = local_config.llm.reserved_output_tokens

    env: dict[str, str] = {}
    if api_key:
        env[api_key_env] = api_key
        _set_secret_env(env, api_key)
    if api_base:
        env[api_base_env] = api_base
        _set_api_base_env(env, api_base)
    model = local_config.llm.model
    if model:
        env["FEATURELIFTBENCH_MODEL"] = model
        env["MSWEA_MODEL_NAME"] = model
    env.setdefault("MSWEA_CONFIGURED", "true")
    env.setdefault("MSWEA_GLOBAL_COST_LIMIT", "0")
    env.setdefault("MSWEA_GLOBAL_CALL_LIMIT", "0")

    if local_config.llm.context_window_tokens is not None:
        env["FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS"] = str(local_config.llm.context_window_tokens)
    env["FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS"] = str(local_config.llm.reserved_output_tokens)

    if local_config.llm.native_tool_calling is not None:
        env["LLM_NATIVE_TOOL_CALLING"] = (
            "true" if local_config.llm.native_tool_calling else "false"
        )

    openhands_command = _resolve_openhands_command(
        AgentRunConfig(agent=local_config.agent.kind),
        profile=profile,
        env_values=env_values,
    )

    run_config = AgentRunConfig(
        agent=local_config.agent.kind,
        model=model,
        timeout_seconds=local_config.agent.timeout_seconds,
        command=openhands_command,
        extra_args=_merge_extra_args(()),
        env=apply_openhands_llm_env(env) if _is_openhands_agent(local_config.agent.kind) else env,
        profile="flb.local",
    )
    summary = {
        "config_path": str(local_config.config_path),
        "profile": "flb.local",
        "env_file": str(local_config.env_file.resolve()),
        "model": model or "",
        "agent_bin": "",
        "api_key_env": api_key_env,
        "api_base_env": api_base_env,
        "api_key_present": bool(api_key),
        "api_key_source": api_key_source,
        "api_key_environment_overrides_env_file": api_key_env_conflict,
        "api_base": api_base or "",
        "api_base_source": "flb.local.toml" if api_base else "missing",
        "api_base_environment_overrides_env_file": api_base_env_conflict,
        "cost_limit": "0",
        "call_limit": "0",
        "cost_tracking": "",
        "context_window_tokens": local_config.llm.context_window_tokens or "",
        "reserved_output_tokens": local_config.llm.reserved_output_tokens,
        "openhands_command": openhands_command if _is_openhands_agent(local_config.agent.kind) else "",
        "openhands_command_configured": bool(openhands_command)
        if _is_openhands_agent(local_config.agent.kind)
        else False,
    }
    return LoadedAgentConfig(run_config=run_config, summary=summary)


def resolve_output_dir(
    local_config: LocalConfig,
    *,
    suite_preset: SuitePreset,
    resume_dir: Path | None = None,
) -> Path:
    if resume_dir is not None:
        return resume_dir.resolve()
    if local_config.run.output_dir:
        return Path(local_config.run.output_dir).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_name = f"{suite_preset.name}-{timestamp}"
    model = local_config.llm.model or "unknown-model"
    return resolve_openhands_run_dir(
        track="python",
        model=model,
        suite_name=suite_preset.name,
        run_name=run_name,
    )


def local_config_fingerprint(local_config: LocalConfig) -> str:
    digest = hashlib.sha256(local_config.config_path.read_bytes()).hexdigest()
    return digest[:16]


def write_run_meta(
    output_dir: Path,
    *,
    local_config: LocalConfig,
    suite_preset: SuitePreset,
    resumed: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "suite": suite_preset.name,
        "model": local_config.llm.model,
        "base_url": local_config.llm.base_url,
        "agent": local_config.agent.kind,
        "config_path": str(local_config.config_path),
        "config_fingerprint": local_config_fingerprint(local_config),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "resumed": resumed,
    }
    meta_path = output_dir / "run.meta.json"
    meta_path.write_text(
        __import__("json").dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta_path


def apply_local_overrides(
    local_config: LocalConfig,
    *,
    suite: str | None = None,
    max_steps: int | None = None,
    workers: int | None = None,
    output_dir: str | None = None,
) -> LocalConfig:
    run = local_config.run
    agent = local_config.agent
    if suite is not None:
        if suite not in SUITE_NAMES:
            raise ValueError(f"suite must be one of: {', '.join(sorted(SUITE_NAMES))}")
        run = LocalRunConfig(
            suite=suite,
            workers=run.workers,
            output_dir=run.output_dir,
            agent_docker=run.agent_docker,
            eval_docker=run.eval_docker,
            extra_agent_passes=run.extra_agent_passes,
            retry_rate_limit=run.retry_rate_limit,
            task_cooldown_seconds=run.task_cooldown_seconds,
            custom_task_root=run.custom_task_root,
            custom_task_ids=run.custom_task_ids,
        )
    if workers is not None:
        run = LocalRunConfig(
            suite=run.suite,
            workers=max(1, workers),
            output_dir=run.output_dir,
            agent_docker=run.agent_docker,
            eval_docker=run.eval_docker,
            extra_agent_passes=run.extra_agent_passes,
            retry_rate_limit=run.retry_rate_limit,
            task_cooldown_seconds=run.task_cooldown_seconds,
            custom_task_root=run.custom_task_root,
            custom_task_ids=run.custom_task_ids,
        )
    if output_dir is not None:
        run = LocalRunConfig(
            suite=run.suite,
            workers=run.workers,
            output_dir=output_dir,
            agent_docker=run.agent_docker,
            eval_docker=run.eval_docker,
            extra_agent_passes=run.extra_agent_passes,
            retry_rate_limit=run.retry_rate_limit,
            task_cooldown_seconds=run.task_cooldown_seconds,
            custom_task_root=run.custom_task_root,
            custom_task_ids=run.custom_task_ids,
        )
    if max_steps is not None:
        agent = LocalAgentConfig(
            kind=agent.kind,
            max_steps=max(1, max_steps),
            timeout_seconds=agent.timeout_seconds,
        )
    return LocalConfig(
        llm=local_config.llm,
        agent=agent,
        run=run,
        config_path=local_config.config_path,
        env_file=local_config.env_file,
    )


def _infer_api_base_env(api_key_env: str) -> str:
    if api_key_env.endswith("_API_KEY"):
        return api_key_env[: -len("_API_KEY")] + "_API_BASE"
    return "FEATURELIFTBENCH_API_BASE"


def _config_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return _truthy(value)


def _float_value(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, float(value))
    if isinstance(value, str) and value.strip():
        try:
            return max(0.0, float(value.strip()))
        except ValueError:
            return 0.0
    return 0.0
