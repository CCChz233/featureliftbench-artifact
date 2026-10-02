"""Shared agent API configuration loading."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ablation import resolve_ablation_options
from .agent_adapters import AgentRunConfig
from .contract_closure_gate.common import PRIMARY_MAX_STEPS_ENV
from .contract_closure_gate.common import PRIMARY_TOKEN_LIMIT_ENV
from .contract_closure_gate.common import REPAIR_MAX_STEPS_ENV
from .contract_closure_gate.common import REPAIR_TOKEN_LIMIT_ENV
from .contract_closure_gate.common import INFRA_RETRY_LIMIT_ENV
from .contract_closure_gate.common import INFRA_RETRY_MAX_STEPS_ENV
from .contract_closure_gate.common import LITE_V1_SILENT_FINISH_ENV
from .llm_usage_proxy import TOTAL_TOKEN_LIMIT_ENV
from .llm_usage_proxy import TOOL_ALIAS_COMPAT_ENV
from .openhands_usage import CONDENSER_ATTENTION_WINDOW_ENV
from .openhands_usage import CONDENSER_KEEP_FIRST_ENV
from .openhands_usage import CONDENSER_MAX_EVENTS_ENV
from .openhands_usage import CONDENSER_MODE_ENV
from .openhands_usage import CONTEXT_WINDOW_ENV
from .openhands_usage import CUSTOM_CONDENSER_MODES
from .openhands_usage import DEFAULT_CONDENSER_ATTENTION_WINDOW
from .openhands_usage import DEFAULT_CONDENSER_KEEP_FIRST
from .openhands_usage import DEFAULT_CONDENSER_MAX_EVENTS
from .openhands_usage import KNOWN_CONDENSER_MODES
from .openhands_usage import RESERVED_OUTPUT_ENV
from .openhands_usage import SEEDED_CONDENSER_MODES
from .paths import DEFAULT_AGENT_CONFIG
from .repo_graph.policy import BOOTSTRAP_MAX_CHARS_ENV
from .repo_graph.policy import BOOTSTRAP_MAX_NODES_ENV
from .repo_graph.policy import BOOTSTRAP_STYLE_ENV
from .repo_graph.policy import BUDGET_TOKENS_ENV
from .repo_graph.policy import CACHE_DIR_ENV as REPO_GRAPH_CACHE_DIR_ENV
from .repo_graph.policy import FAIL_FAST_ENV
from .repo_graph.policy import INSPECT_MAX_CHARS_ENV
from .repo_graph.policy import MODE_ENV as REPO_GRAPH_MODE_ENV
from .repo_graph.policy import QUERY_MAX_CHARS_ENV
from .repo_graph.policy import TRANSPORT_ENV
from .repo_graph.policy import VIEW_ENV
from .repo_graph.policy import RepoGraphPolicy
from .source_ablation import ISOLATION_ENV as SOURCE_ABLATION_ISOLATION_ENV
from .source_ablation import isolation_enabled as source_ablation_isolation_enabled


DEFAULT_API_KEY_ENV = "FEATURELIFTBENCH_API_KEY"
DEFAULT_API_BASE_ENV = "FEATURELIFTBENCH_API_BASE"
DEFAULT_OPENHANDS_COMMAND_ENV = "FEATURELIFTBENCH_OPENHANDS_COMMAND"
OPENHANDS_MAX_STEPS_ENV = "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"
LLM_MAX_MESSAGE_CHARS_ENV = "LLM_MAX_MESSAGE_CHARS"
DEFAULT_OPENHANDS_COMMAND = (
    "openhands --headless --override-with-envs --exit-without-confirmation "
    "-f {prompt_file} --json"
)


@dataclass(frozen=True)
class LoadedAgentConfig:
    """Resolved agent configuration with secrets excluded from summaries."""

    run_config: AgentRunConfig
    summary: dict[str, Any]


def load_agent_run_config(
    *,
    base_config: AgentRunConfig,
    config_path: str | Path | None = None,
    profile_name: str | None = None,
    env_file: str | Path | None = None,
    mount_public_tests: bool | None = None,
    prompt_style: str | None = None,
    expose_source_hints: bool | None = None,
    source_context: str | None = None,
    td_cognition: bool | None = None,
    exec_contract: bool | None = None,
    exec_contract_variant: str | None = None,
    self_contract: bool | None = None,
    test_first_lift: bool | None = None,
    contract_closure_gate: bool | None = None,
    contract_closure_gate_lite: bool | None = None,
    contract_closure_gate_lite_v1: bool | None = None,
    contract_closure_gate_lite_rescue: bool | None = None,
    contract_closure_gate_lite_rescue_plus: bool | None = None,
    contract_closure_gate_v3: bool | None = None,
    contract_closure_budget_control: bool | None = None,
    adaptive_budget_v2: bool | None = None,
    pre_submit_contract_audit: bool | None = None,
    spec_adversarial_self_test: bool | None = None,
    obligation_guided: bool | None = None,
    cgvl: bool | None = None,
) -> LoadedAgentConfig:
    """Load shared agent config and merge it into a run config.

    Precedence is:
    CLI options > process env > environment file > profile defaults.
    """

    data = _read_toml(config_path)
    selected_profile = profile_name or _string_value(data.get("profile")) or "default"
    profiles = data.get("profiles")
    profile = profiles.get(selected_profile, {}) if isinstance(profiles, dict) else {}
    if not isinstance(profile, dict):
        raise ValueError(f"agent profile must be a table: {selected_profile}")
    rsg_table = data.get("rsg") if isinstance(data.get("rsg"), dict) else {}

    config_env_file = env_file or _string_value(data.get("env_file")) or ".env"
    env_values = _read_env_file(config_env_file)
    ablation = resolve_ablation_options(
        profile=profile,
        env_values=env_values,
        process_env=os.environ,
        mount_public_tests=mount_public_tests,
        prompt_style=prompt_style,
        expose_source_hints=expose_source_hints,
        source_context=source_context,
        td_cognition=td_cognition,
        exec_contract=exec_contract,
        exec_contract_variant=exec_contract_variant,
        self_contract=self_contract,
        test_first_lift=test_first_lift,
        contract_closure_gate=contract_closure_gate,
        contract_closure_gate_lite=contract_closure_gate_lite,
        contract_closure_gate_lite_v1=contract_closure_gate_lite_v1,
        contract_closure_gate_lite_rescue=contract_closure_gate_lite_rescue,
        contract_closure_gate_lite_rescue_plus=(
            contract_closure_gate_lite_rescue_plus
        ),
        contract_closure_gate_v3=contract_closure_gate_v3,
        contract_closure_budget_control=contract_closure_budget_control,
        adaptive_budget_v2=adaptive_budget_v2,
        pre_submit_contract_audit=pre_submit_contract_audit,
        spec_adversarial_self_test=spec_adversarial_self_test,
        obligation_guided=obligation_guided,
        cgvl=cgvl,
    )

    api_key_env = _string_value(profile.get("api_key_env")) or DEFAULT_API_KEY_ENV
    api_base_env = _string_value(profile.get("api_base_env")) or DEFAULT_API_BASE_ENV
    api_key, api_key_source = _first_non_empty_with_source(
        ("environment", os.environ.get(api_key_env)),
        (".env", env_values.get(api_key_env)),
    )
    api_base, api_base_source = _first_non_empty_with_source(
        ("environment", os.environ.get(api_base_env)),
        (".env", env_values.get(api_base_env)),
        ("profile", _string_value(profile.get("api_base"))),
        ("profile", _string_value(profile.get("base_url"))),
    )
    api_key_env_conflict = _has_env_file_conflict(api_key_env, env_values)
    api_base_env_conflict = _has_env_file_conflict(api_base_env, env_values)
    model = _first_non_empty(base_config.model, _string_value(profile.get("model")))
    profile_agent_bin = _string_value(profile.get("agent_bin"))
    if _ignores_profile_agent_bin(base_config.agent):
        agent_bin = base_config.agent_bin
    else:
        agent_bin = _first_non_empty(base_config.agent_bin, profile_agent_bin)

    env = dict(base_config.env or {})
    for key, value in _agent_env_values(
        env_values,
        api_key_env=api_key_env,
        api_base_env=api_base_env,
    ).items():
        env.setdefault(key, value)
    if api_key:
        env.setdefault(api_key_env, api_key)
        _set_secret_env(env, api_key)
    if api_base:
        env.setdefault(api_base_env, api_base)
        _set_api_base_env(env, api_base)
    if model:
        env.setdefault("FEATURELIFTBENCH_MODEL", model)
        env.setdefault("MSWEA_MODEL_NAME", model)
    env.setdefault("MSWEA_CONFIGURED", "true")

    cost_limit = _string_value(profile.get("cost_limit"))
    call_limit = _string_value(profile.get("call_limit"))
    cost_tracking = _string_value(profile.get("cost_tracking"))
    if cost_limit:
        env.setdefault("MSWEA_GLOBAL_COST_LIMIT", cost_limit)
    if call_limit:
        env.setdefault("MSWEA_GLOBAL_CALL_LIMIT", call_limit)
    if cost_tracking:
        env.setdefault("MSWEA_COST_TRACKING", cost_tracking)

    context_mode = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=CONDENSER_MODE_ENV,
        profile_value=profile.get("openhands_condenser_mode"),
    ).lower()
    if context_mode and context_mode not in KNOWN_CONDENSER_MODES:
        raise ValueError(f"unknown OpenHands condenser mode: {context_mode}")

    context_window_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=CONTEXT_WINDOW_ENV,
        profile_value=profile.get("context_window_tokens"),
    )
    reserved_output_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=RESERVED_OUTPUT_ENV,
        profile_value=profile.get("reserved_output_tokens"),
    )
    context_window_tokens = _positive_int_value(context_window_raw)
    reserved_output_tokens = _positive_int_value(reserved_output_raw)

    keep_first_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=CONDENSER_KEEP_FIRST_ENV,
        profile_value=profile.get("openhands_condenser_keep_first"),
    )
    max_events_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=CONDENSER_MAX_EVENTS_ENV,
        profile_value=profile.get("openhands_condenser_max_events"),
    )
    keep_first = _non_negative_int_value(keep_first_raw)
    max_events = _positive_int_value(max_events_raw)

    attention_window_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=CONDENSER_ATTENTION_WINDOW_ENV,
        profile_value=profile.get("openhands_condenser_attention_window"),
    )
    attention_window = _positive_int_value(attention_window_raw)

    if context_mode in SEEDED_CONDENSER_MODES:
        if not _is_openhands_agent(base_config.agent):
            raise ValueError("OpenHands token condenser mode requires an OpenHands agent")
        if context_window_tokens is None or reserved_output_tokens is None:
            raise ValueError(
                "OpenHands token condenser mode requires positive "
                "context_window_tokens and reserved_output_tokens"
            )
        if context_window_tokens <= reserved_output_tokens:
            raise ValueError(
                "OpenHands token condenser mode requires context_window_tokens > "
                "reserved_output_tokens"
            )
        if keep_first_raw and keep_first is None:
            raise ValueError("openhands_condenser_keep_first must be a non-negative integer")
        if max_events_raw and max_events is None:
            raise ValueError("openhands_condenser_max_events must be a positive integer")
        keep_first = (
            DEFAULT_CONDENSER_KEEP_FIRST if keep_first is None else keep_first
        )
        max_events = DEFAULT_CONDENSER_MAX_EVENTS if max_events is None else max_events
        attention_window = (
            DEFAULT_CONDENSER_ATTENTION_WINDOW
            if attention_window is None
            else attention_window
        )
        env[CONDENSER_MODE_ENV] = context_mode
        env[CONDENSER_KEEP_FIRST_ENV] = str(keep_first)
        env[CONDENSER_MAX_EVENTS_ENV] = str(max_events)
        env[CONDENSER_ATTENTION_WINDOW_ENV] = str(attention_window)
        env["FEATURELIFTBENCH_AGENT_PROFILE"] = selected_profile

    if context_window_tokens is not None:
        env[CONTEXT_WINDOW_ENV] = str(context_window_tokens)
    elif context_mode in SEEDED_CONDENSER_MODES:
        raise ValueError("context_window_tokens must be a positive integer")
    if reserved_output_tokens is not None:
        env[RESERVED_OUTPUT_ENV] = str(reserved_output_tokens)
    elif context_mode in SEEDED_CONDENSER_MODES:
        raise ValueError("reserved_output_tokens must be a positive integer")

    repo_graph_values = {
        REPO_GRAPH_MODE_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=REPO_GRAPH_MODE_ENV,
            profile_value=profile.get("repo_graph_mode"),
        ),
        TRANSPORT_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=TRANSPORT_ENV,
            profile_value=profile.get("repo_graph_transport"),
        ),
        FAIL_FAST_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=FAIL_FAST_ENV,
            profile_value=profile.get("repo_graph_fail_fast"),
        ),
        BOOTSTRAP_MAX_NODES_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=BOOTSTRAP_MAX_NODES_ENV,
            profile_value=profile.get("repo_graph_bootstrap_max_nodes"),
        ),
        BOOTSTRAP_MAX_CHARS_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=BOOTSTRAP_MAX_CHARS_ENV,
            profile_value=profile.get("repo_graph_bootstrap_max_chars"),
        ),
        QUERY_MAX_CHARS_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=QUERY_MAX_CHARS_ENV,
            profile_value=profile.get("repo_graph_query_max_chars"),
        ),
        REPO_GRAPH_CACHE_DIR_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=REPO_GRAPH_CACHE_DIR_ENV,
            profile_value=profile.get("repo_graph_cache_dir"),
        ),
        BOOTSTRAP_STYLE_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=BOOTSTRAP_STYLE_ENV,
            profile_value=_coalesce_profile_value(
                profile.get("rsg_bootstrap"),
                rsg_table.get("bootstrap"),
            ),
        ),
        VIEW_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=VIEW_ENV,
            profile_value=_coalesce_profile_value(
                profile.get("rsg_view"),
                rsg_table.get("view"),
            ),
        ),
        BUDGET_TOKENS_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=BUDGET_TOKENS_ENV,
            profile_value=_coalesce_profile_value(
                profile.get("rsg_budget_tokens"),
                rsg_table.get("budget_tokens"),
            ),
        ),
        INSPECT_MAX_CHARS_ENV: _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=INSPECT_MAX_CHARS_ENV,
            profile_value=_coalesce_profile_value(
                profile.get("rsg_inspect_max_chars"),
                rsg_table.get("inspect_max_chars"),
            ),
        ),
    }
    explicit_repo_graph = any(value for value in repo_graph_values.values())
    # Top-level [rsg] enabled=true implies mode=static when no legacy mode is set.
    if (
        not repo_graph_values[REPO_GRAPH_MODE_ENV]
        and _truthy(rsg_table.get("enabled"))
    ):
        repo_graph_values[REPO_GRAPH_MODE_ENV] = "static"
        explicit_repo_graph = True
    if (
        not repo_graph_values[TRANSPORT_ENV]
        and _string_value(rsg_table.get("transport"))
    ):
        repo_graph_values[TRANSPORT_ENV] = _string_value(rsg_table.get("transport"))
        explicit_repo_graph = True
    repo_graph_policy = RepoGraphPolicy.from_env(repo_graph_values)
    if explicit_repo_graph:
        env[REPO_GRAPH_MODE_ENV] = repo_graph_policy.mode
        env[TRANSPORT_ENV] = repo_graph_policy.transport
        env[FAIL_FAST_ENV] = "true" if repo_graph_policy.fail_fast else "false"
        env[BOOTSTRAP_MAX_NODES_ENV] = str(repo_graph_policy.bootstrap_max_nodes)
        env[BOOTSTRAP_MAX_CHARS_ENV] = str(repo_graph_policy.bootstrap_max_chars)
        env[QUERY_MAX_CHARS_ENV] = str(repo_graph_policy.query_max_chars)
        env[BOOTSTRAP_STYLE_ENV] = repo_graph_policy.bootstrap
        env[VIEW_ENV] = repo_graph_policy.view
        env[BUDGET_TOKENS_ENV] = str(repo_graph_policy.budget_tokens)
        env[INSPECT_MAX_CHARS_ENV] = str(repo_graph_policy.inspect_max_chars)
        if repo_graph_values[REPO_GRAPH_CACHE_DIR_ENV]:
            env[REPO_GRAPH_CACHE_DIR_ENV] = repo_graph_values[REPO_GRAPH_CACHE_DIR_ENV]

    native_tool_calling = profile.get("native_tool_calling")
    if _is_openhands_agent(base_config.agent) and native_tool_calling is not None:
        env.setdefault(
            "LLM_NATIVE_TOOL_CALLING",
            "true" if _truthy(native_tool_calling) else "false",
        )
    tool_alias_compat_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=TOOL_ALIAS_COMPAT_ENV,
        profile_value=profile.get("openhands_tool_alias_compat"),
    )
    tool_alias_compat = _truthy(tool_alias_compat_raw)
    if _is_openhands_agent(base_config.agent) and tool_alias_compat_raw:
        env[TOOL_ALIAS_COMPAT_ENV] = "1" if tool_alias_compat else "0"
    openhands_max_steps = _positive_int_value(
        _resolve_profile_env_value(
            base_config=base_config,
            env_values=env_values,
            env_name=OPENHANDS_MAX_STEPS_ENV,
            profile_value=profile.get("openhands_max_steps"),
        )
    )
    if _is_openhands_agent(base_config.agent) and openhands_max_steps is not None:
        env[OPENHANDS_MAX_STEPS_ENV] = str(openhands_max_steps)

    openhands_budget_values: dict[str, int] = {}
    for env_name, profile_key in (
        (TOTAL_TOKEN_LIMIT_ENV, "openhands_total_token_limit"),
        (LLM_MAX_MESSAGE_CHARS_ENV, "llm_max_message_chars"),
        (PRIMARY_TOKEN_LIMIT_ENV, "contract_closure_primary_token_limit"),
        (REPAIR_TOKEN_LIMIT_ENV, "contract_closure_repair_token_limit"),
        (PRIMARY_MAX_STEPS_ENV, "contract_closure_primary_max_steps"),
        (REPAIR_MAX_STEPS_ENV, "contract_closure_repair_max_steps"),
        (INFRA_RETRY_LIMIT_ENV, "contract_closure_infra_retry_limit"),
        (
            INFRA_RETRY_MAX_STEPS_ENV,
            "contract_closure_infra_retry_max_trigger_steps",
        ),
    ):
        value = _positive_int_value(
            _resolve_profile_env_value(
                base_config=base_config,
                env_values=env_values,
                env_name=env_name,
                profile_value=profile.get(profile_key),
            )
        )
        if _is_openhands_agent(base_config.agent) and value is not None:
            env[env_name] = str(value)
            openhands_budget_values[env_name] = value

    env.update(ablation.to_env())
    # Supplementary isolation is a process/CLI concern. Copy it into config.env
    # so Docker mounts and run.json see the same flag. Official Main omits it.
    if source_ablation_isolation_enabled(os.environ) or source_ablation_isolation_enabled(env):
        env[SOURCE_ABLATION_ISOLATION_ENV] = "1"
    silent_finish_raw = _resolve_profile_env_value(
        base_config=base_config,
        env_values=env_values,
        env_name=LITE_V1_SILENT_FINISH_ENV,
        profile_value=profile.get("lite_v1_silent_finish"),
    )
    if _truthy(silent_finish_raw):
        env[LITE_V1_SILENT_FINISH_ENV] = "1"

    extra_args = _merge_extra_args(
        _featurelift_profile_extra_args(profile, agent=base_config.agent),
        base_config.extra_args,
    )
    openhands_command = _resolve_openhands_command(
        base_config,
        profile=profile,
        env_values=env_values,
    )

    run_config = AgentRunConfig(
        agent=base_config.agent,
        agent_bin=agent_bin,
        model=model,
        config=base_config.config or _string_value(profile.get("agent_config")),
        yolo=base_config.yolo,
        timeout_seconds=base_config.timeout_seconds,
        step_limit=base_config.step_limit,
        command=openhands_command,
        extra_args=extra_args,
        env=env,
        profile=selected_profile,
    )
    summary = {
        "config_path": str(Path(config_path).resolve()) if config_path else "",
        "profile": selected_profile,
        "env_file": str(Path(config_env_file).resolve()) if config_env_file else "",
        "model": model or "",
        "agent_bin": agent_bin or "",
        "api_key_env": api_key_env,
        "api_base_env": api_base_env,
        "api_key_present": bool(api_key),
        "api_key_source": api_key_source,
        "api_key_environment_overrides_env_file": api_key_env_conflict,
        "api_base": api_base or "",
        "api_base_source": api_base_source,
        "api_base_environment_overrides_env_file": api_base_env_conflict,
        "cost_limit": cost_limit or "",
        "call_limit": call_limit or "",
        "step_limit": base_config.step_limit or "",
        "cost_tracking": cost_tracking or "",
        "context_window_tokens": context_window_tokens or "",
        "reserved_output_tokens": reserved_output_tokens or "",
        "openhands_condenser_mode": context_mode or "default",
        "openhands_condenser_trigger_tokens": (
            context_window_tokens - reserved_output_tokens
            if context_mode in SEEDED_CONDENSER_MODES
            and context_window_tokens is not None
            and reserved_output_tokens is not None
            else ""
        ),
        "openhands_condenser_target_tokens": (
            (context_window_tokens - reserved_output_tokens) // 2
            if context_mode in SEEDED_CONDENSER_MODES
            and context_window_tokens is not None
            and reserved_output_tokens is not None
            else ""
        ),
        "openhands_condenser_keep_first": keep_first if context_mode in SEEDED_CONDENSER_MODES else "",
        "openhands_condenser_max_events": max_events if context_mode in SEEDED_CONDENSER_MODES else "",
        "openhands_condenser_attention_window": (
            attention_window if context_mode in CUSTOM_CONDENSER_MODES else ""
        ),
        "openhands_command": openhands_command if _is_openhands_agent(base_config.agent) else "",
        "openhands_command_configured": bool(openhands_command)
        if _is_openhands_agent(base_config.agent)
        else False,
        "openhands_max_steps": openhands_max_steps or "",
        "llm_max_message_chars": openhands_budget_values.get(
            LLM_MAX_MESSAGE_CHARS_ENV, ""
        ),
        "openhands_total_token_limit": openhands_budget_values.get(
            TOTAL_TOKEN_LIMIT_ENV, ""
        ),
        "contract_closure_primary_token_limit": openhands_budget_values.get(
            PRIMARY_TOKEN_LIMIT_ENV, ""
        ),
        "contract_closure_repair_token_limit": openhands_budget_values.get(
            REPAIR_TOKEN_LIMIT_ENV, ""
        ),
        "contract_closure_primary_max_steps": openhands_budget_values.get(
            PRIMARY_MAX_STEPS_ENV, ""
        ),
        "contract_closure_repair_max_steps": openhands_budget_values.get(
            REPAIR_MAX_STEPS_ENV, ""
        ),
        "contract_closure_infra_retry_limit": openhands_budget_values.get(
            INFRA_RETRY_LIMIT_ENV, ""
        ),
        "contract_closure_infra_retry_max_trigger_steps": openhands_budget_values.get(
            INFRA_RETRY_MAX_STEPS_ENV, ""
        ),
        "native_tool_calling": (
            env.get("LLM_NATIVE_TOOL_CALLING", "") if _is_openhands_agent(base_config.agent) else ""
        ),
        "openhands_tool_alias_compat": (
            tool_alias_compat if _is_openhands_agent(base_config.agent) else False
        ),
        "repo_graph_mode": repo_graph_policy.mode,
        "repo_graph_transport": repo_graph_policy.transport,
        "repo_graph_fail_fast": repo_graph_policy.fail_fast,
        "repo_graph_bootstrap_max_nodes": repo_graph_policy.bootstrap_max_nodes,
        "repo_graph_bootstrap_max_chars": repo_graph_policy.bootstrap_max_chars,
        "repo_graph_query_max_chars": repo_graph_policy.query_max_chars,
        "repo_graph_cache_configured": bool(repo_graph_values[REPO_GRAPH_CACHE_DIR_ENV]),
        "rsg_bootstrap": repo_graph_policy.bootstrap,
        "rsg_view": repo_graph_policy.view,
        "rsg_budget_tokens": repo_graph_policy.budget_tokens,
        "rsg_inspect_max_chars": repo_graph_policy.inspect_max_chars,
        "ablation_arm": ablation.ablation_arm,
        "mount_public_tests": ablation.mount_public_tests,
        "prompt_style": ablation.prompt_style,
        "expose_source_hints": ablation.expose_source_hints,
        "source_context": ablation.source_context,
        "td_cognition": ablation.td_cognition,
        "exec_contract": ablation.exec_contract,
        "exec_contract_variant": ablation.exec_contract_variant,
        "self_contract": ablation.self_contract,
        "test_first_lift": ablation.test_first_lift,
        "contract_closure_gate": ablation.contract_closure_gate,
        "contract_closure_gate_lite": ablation.contract_closure_gate_lite,
        "contract_closure_gate_lite_v1": (
            ablation.contract_closure_gate_lite_v1
        ),
        "lite_v1_silent_finish": env.get(LITE_V1_SILENT_FINISH_ENV) == "1",
        "contract_closure_gate_lite_rescue": (
            ablation.contract_closure_gate_lite_rescue
        ),
        "contract_closure_gate_lite_rescue_plus": (
            ablation.contract_closure_gate_lite_rescue_plus
        ),
        "contract_closure_gate_v3": ablation.contract_closure_gate_v3,
        "contract_closure_budget_control": (
            ablation.contract_closure_budget_control
        ),
        "adaptive_budget_v2": ablation.adaptive_budget_v2,
        "pre_submit_contract_audit": ablation.pre_submit_contract_audit,
        "spec_adversarial_self_test": ablation.spec_adversarial_self_test,
        "obligation_guided": ablation.obligation_guided,
        "cgvl": ablation.cgvl,
    }
    return LoadedAgentConfig(run_config=run_config, summary=summary)


def _read_toml(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        config_path = DEFAULT_AGENT_CONFIG
        if not config_path.exists():
            return {}
        path = config_path
    config_path = Path(path)
    if not config_path.exists():
        raise ValueError(f"agent config file not found: {config_path}")
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid agent config TOML: {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"agent config must be a TOML table: {config_path}")
    return data


def _read_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if key:
            values[key] = value
    return values


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _set_secret_env(env: dict[str, str], api_key: str) -> None:
    env.setdefault("FEATURELIFTBENCH_API_KEY", api_key)
    env.setdefault("OPENAI_API_KEY", api_key)
    env.setdefault("LITELLM_API_KEY", api_key)
    env.setdefault("DEEPSEEK_API_KEY", api_key)


def _set_api_base_env(env: dict[str, str], api_base: str) -> None:
    env.setdefault("FEATURELIFTBENCH_API_BASE", api_base)
    env.setdefault("OPENAI_BASE_URL", api_base)
    env.setdefault("OPENAI_API_BASE", api_base)
    env.setdefault("DEEPSEEK_API_BASE", api_base)


def _agent_env_values(
    env_values: dict[str, str],
    *,
    api_key_env: str,
    api_base_env: str,
) -> dict[str, str]:
    """Return the non-secret .env values safe to pass into an agent container."""

    selected = {api_key_env, api_base_env}
    forwarded: dict[str, str] = {}
    for key, value in env_values.items():
        if key in selected:
            forwarded[key] = value
            continue
        if not key.startswith("FEATURELIFTBENCH_"):
            continue
        if _is_api_credential_env(key) or _is_api_base_env(key):
            continue
        forwarded[key] = value
    return forwarded


def _is_api_credential_env(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))


def _is_api_base_env(key: str) -> bool:
    upper = key.upper()
    return upper.endswith("_API_BASE") or upper.endswith("_BASE_URL")


def _string_value(value: Any) -> str:
    return value if isinstance(value, str) and value else ""


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""


def _first_non_empty_with_source(*values: tuple[str, str | None]) -> tuple[str, str]:
    for source, value in values:
        if value:
            return value, source
    return "", "missing"


def _has_env_file_conflict(key: str, env_values: dict[str, str]) -> bool:
    process_value = os.environ.get(key)
    file_value = env_values.get(key)
    return bool(process_value and file_value and process_value != file_value)


def _positive_int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _non_negative_int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _resolve_profile_env_value(
    *,
    base_config: AgentRunConfig,
    env_values: dict[str, str],
    env_name: str,
    profile_value: Any,
) -> str:
    """Resolve one non-secret run setting using the documented precedence."""

    base_env = base_config.env or {}
    profile_text = "" if profile_value is None else str(profile_value).strip()
    return _first_non_empty(
        base_env.get(env_name),
        os.environ.get(env_name),
        env_values.get(env_name),
        profile_text,
    )


def _coalesce_profile_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _is_featurelift_agent(agent: str) -> bool:
    normalized = agent.strip().lower().replace("_", "-")
    return normalized in {"featurelift-agent", "featureliftagent", "featurelift"}


def _is_openhands_agent(agent: str) -> bool:
    normalized = agent.strip().lower().replace("_", "-")
    return normalized in {"openhands", "openhands-agent", "openhandsagent"}


def _ignores_profile_agent_bin(agent: str) -> bool:
    return _is_featurelift_agent(agent) or _is_openhands_agent(agent)


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value != 0:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _featurelift_profile_extra_args(profile: dict[str, Any], *, agent: str) -> tuple[str, ...]:
    if not _is_featurelift_agent(agent):
        return ()
    args: list[str] = []
    if _truthy(profile.get("featurelift_enable_llm")):
        args.append("--enable-llm")
    if _truthy(profile.get("featurelift_execute_actions")):
        args.append("--execute-actions")
    phases = _string_value(profile.get("featurelift_llm_phases"))
    if phases:
        args.extend(["--llm-phases", phases])
    repair_rounds = profile.get("featurelift_max_repair_rounds")
    if repair_rounds is not None and str(repair_rounds).strip():
        args.extend(["--max-repair-rounds", str(repair_rounds).strip()])
    tool_timeout = profile.get("featurelift_tool_timeout")
    if tool_timeout is not None and str(tool_timeout).strip():
        args.extend(["--tool-timeout", str(tool_timeout).strip()])
    return tuple(args)


def _merge_extra_args(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group)
    return tuple(merged)


def _resolve_openhands_command(
    base_config: AgentRunConfig,
    *,
    profile: dict[str, Any],
    env_values: dict[str, str],
) -> str:
    if not _is_openhands_agent(base_config.agent):
        return base_config.command
    if base_config.command:
        return base_config.command
    profile_command = _string_value(profile.get("openhands_command"))
    if profile_command:
        return profile_command
    return _first_non_empty(
        os.environ.get(DEFAULT_OPENHANDS_COMMAND_ENV),
        env_values.get(DEFAULT_OPENHANDS_COMMAND_ENV),
        DEFAULT_OPENHANDS_COMMAND,
    )
