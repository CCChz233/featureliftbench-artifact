"""Register custom condensers with the OpenHands CLI agent store."""

from __future__ import annotations

from typing import Any

CUSTOM_CONDENSER_KINDS = frozenset(
    {
        "RecencyMaskingCondenser",
        "ArtifactAwareCondenser",
        "VerificationAwareCondenser",
    }
)


def apply_openhands_condenser_patch() -> None:
    """Keep FeatureLiftBench condensers instead of stripping non-LLM kinds.

    OpenHands 1.16 drops any condenser that is not ``LLMSummarizingCondenser``
    in two places: ``_apply_env_overrides`` (``--override-with-envs``) and
    ``_maybe_build_condenser``. Patching only the second still yields
    ``condenser=None`` at runtime.
    """

    from featureliftbench.openhands_condenser import kinds as _kinds

    _ = _kinds
    store = _resolve_agent_store()
    if store is None:
        return
    if hasattr(store, "_maybe_build_condenser"):
        original_build = store._maybe_build_condenser

        def _maybe_build_condenser(
            self: Any, agent: Any, *args: Any, **kwargs: Any
        ) -> Any:
            condenser = getattr(agent, "condenser", None)
            if _is_custom_condenser(condenser):
                return condenser
            return original_build(self, agent, *args, **kwargs)

        store._maybe_build_condenser = _maybe_build_condenser
    if hasattr(store, "_apply_env_overrides"):
        original_overrides = store._apply_env_overrides

        def _apply_env_overrides(
            self: Any, agent: Any, overrides: Any, *args: Any, **kwargs: Any
        ) -> Any:
            condenser = getattr(agent, "condenser", None)
            updated = original_overrides(self, agent, overrides, *args, **kwargs)
            if not _is_custom_condenser(condenser):
                return updated
            if hasattr(updated, "model_copy"):
                return updated.model_copy(update={"condenser": condenser})
            try:
                updated.condenser = condenser
            except (AttributeError, TypeError):
                return updated
            return updated

        store._apply_env_overrides = _apply_env_overrides


def _is_custom_condenser(condenser: Any) -> bool:
    if condenser is None:
        return False
    return type(condenser).__name__ in CUSTOM_CONDENSER_KINDS


def _resolve_agent_store() -> Any | None:
    candidates = (
        "openhands_cli.stores.agent_store",
        "openhands_cli.ptl.agent_store",
        "openhands_cli.agent_store",
    )
    for module_name in candidates:
        try:
            module = __import__(module_name, fromlist=["AgentStore"])
        except ImportError:
            continue
        store = getattr(module, "AgentStore", None)
        if store is not None:
            return store
    return None
