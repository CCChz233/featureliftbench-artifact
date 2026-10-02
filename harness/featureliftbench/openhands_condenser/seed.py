"""Seed isolated OpenHands agent_settings.json for FeatureLiftBench condensers."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path


def seed_agent_settings() -> None:
    from openhands.sdk.llm import LLM
    from openhands_cli.utils import get_default_cli_agent

    from featureliftbench.openhands_condenser.kinds import ArtifactAwareCondenser
    from featureliftbench.openhands_condenser.kinds import RecencyMaskingCondenser
    from featureliftbench.openhands_condenser.kinds import VerificationAwareCondenser
    from featureliftbench.openhands_condenser.patch import apply_openhands_condenser_patch
    from featureliftbench.openhands_condenser.roles import DEFAULT_ATTENTION_WINDOW

    apply_openhands_condenser_patch()

    out = os.environ["FLB_AGENT_SETTINGS_OUT"]
    meta_out = os.environ["FLB_AGENT_SETTINGS_META_OUT"]
    mode = os.environ.get("FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE", "default")
    token_mode = mode == "token"
    custom_mode = mode in {"recency_masking", "artifact_aware", "verification_aware"}
    native_raw = os.environ.get("LLM_NATIVE_TOOL_CALLING", "true").strip().lower()
    native = native_raw not in {"false", "0", "no", "off"}
    window = os.environ.get("FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS")
    reserved = os.environ.get("FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS")
    trigger = None
    if (token_mode or custom_mode) and window and reserved:
        trigger = int(window) - int(reserved)
    keep_first = int(os.environ.get("FEATURELIFTBENCH_OPENHANDS_CONDENSER_KEEP_FIRST", "4"))
    max_events = int(
        os.environ.get("FEATURELIFTBENCH_OPENHANDS_CONDENSER_MAX_EVENTS", "1000000")
    )
    attention_window = int(
        os.environ.get(
            "FEATURELIFTBENCH_OPENHANDS_CONDENSER_ATTENTION_WINDOW",
            str(DEFAULT_ATTENTION_WINDOW),
        )
    )
    llm = LLM(
        model=os.environ.get("LLM_MODEL", "openai/placeholder"),
        api_key="placeholder",
        usage_id="agent",
        native_tool_calling=native,
        max_input_tokens=trigger,
    )
    agent = get_default_cli_agent(llm)

    def _configure_llm(inner):
        updates = {"native_tool_calling": native}
        if trigger is not None:
            updates["max_input_tokens"] = trigger
        return inner.model_copy(update=updates)

    updates = {"llm": _configure_llm(agent.llm)}
    if mode == "recency_masking":
        updates["condenser"] = RecencyMaskingCondenser(
            attention_window=attention_window,
            max_tokens=trigger,
        )
    elif mode == "artifact_aware":
        updates["condenser"] = ArtifactAwareCondenser(
            max_tokens=trigger,
            attention_window=attention_window,
        )
    elif mode == "verification_aware":
        updates["condenser"] = VerificationAwareCondenser(
            max_tokens=trigger,
        )
    else:
        condenser = getattr(agent, "condenser", None)
        if token_mode and (condenser is None or not hasattr(condenser, "llm")):
            raise RuntimeError("OpenHands LLMSummarizingCondenser is unavailable")
        if condenser is not None and hasattr(condenser, "llm"):
            condenser_updates = {"llm": _configure_llm(condenser.llm)}
            if token_mode:
                condenser_updates.update(
                    {
                        "max_tokens": trigger,
                        "max_size": max_events,
                        "keep_first": keep_first,
                    }
                )
            updates["condenser"] = condenser.model_copy(update=condenser_updates)

    agent = agent.model_copy(update=updates)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(agent.model_dump_json(), encoding="utf-8")

    def _version(name: str) -> str:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    condenser = getattr(agent, "condenser", None)
    metadata = {
        "openhands_version": _version("openhands"),
        "openhands_sdk_version": _version("openhands-sdk"),
        "settings": {
            "agent_max_input_tokens": agent.llm.max_input_tokens,
            "condenser_kind": type(condenser).__name__ if condenser is not None else None,
            "condenser_max_tokens": getattr(condenser, "max_tokens", None),
            "condenser_max_size": getattr(condenser, "max_size", None),
            "condenser_keep_first": getattr(condenser, "keep_first", None),
            "condenser_attention_window": getattr(condenser, "attention_window", None),
            "native_tool_calling": agent.llm.native_tool_calling,
            "same_model_after_environment_override": True,
        },
    }
    Path(meta_out).write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    seed_agent_settings()
