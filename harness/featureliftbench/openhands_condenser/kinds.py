"""OpenHands SDK wrappers around SDK-free condenser rules."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from featureliftbench.openhands_condenser.roles import DEFAULT_ATTENTION_WINDOW
from featureliftbench.openhands_condenser.roles import apply_artifact_aware
from featureliftbench.openhands_condenser.roles import apply_recency_masking
from featureliftbench.openhands_condenser.roles import event_from_mapping
from featureliftbench.openhands_condenser.verification import apply_verification_aware

try:
    from openhands.sdk.context.condenser.base import CondenserBase
    from openhands.sdk.context.view import View
    from openhands.sdk.event.condenser import Condensation
    from openhands.sdk.llm import LLM
except ImportError:  # pragma: no cover - unit tests do not need the SDK
    CondenserBase = object  # type: ignore[misc, assignment]
    View = Any
    Condensation = Any
    LLM = Any


class RecencyMaskingCondenser(CondenserBase):
    """Mask observation bodies outside a recency window."""

    attention_window: int = DEFAULT_ATTENTION_WINDOW
    max_tokens: int | None = None

    def condense(self, view: View, agent_llm: LLM | None = None) -> View | Condensation:
        return _apply_to_view(
            view,
            lambda events: apply_recency_masking(
                events,
                attention_window=int(self.attention_window or DEFAULT_ATTENTION_WINDOW),
            ),
            mode="recency_masking",
        )


class ArtifactAwareCondenser(CondenserBase):
    """Keep persistent latest state; stub unchanged ephemeral re-reads."""

    max_tokens: int | None = None
    attention_window: int = DEFAULT_ATTENTION_WINDOW

    def condense(self, view: View, agent_llm: LLM | None = None) -> View | Condensation:
        trigger = self.max_tokens
        if trigger is None:
            raw = os.environ.get("FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS")
            reserved = os.environ.get("FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS")
            try:
                if raw and reserved:
                    trigger = int(raw) - int(reserved)
            except ValueError:
                trigger = None
        return _apply_to_view(
            view,
            lambda events: apply_artifact_aware(events, trigger_tokens=trigger),
            mode="artifact_aware",
        )


class VerificationAwareCondenser(CondenserBase):
    """Replace old self-test stdout with a compact verification ledger."""

    max_tokens: int | None = None

    def condense(self, view: View, agent_llm: LLM | None = None) -> View | Condensation:
        trigger = self.max_tokens
        if trigger is None:
            raw = os.environ.get("FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS")
            reserved = os.environ.get("FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS")
            try:
                if raw and reserved:
                    trigger = int(raw) - int(reserved)
            except ValueError:
                trigger = None
        return _apply_to_view(
            view,
            lambda events: apply_verification_aware(events, trigger_tokens=trigger),
            mode="verification_aware",
        )


def _apply_to_view(view: View, transform, *, mode: str = "") -> View:
    raw_events = list(getattr(view, "events", []) or [])
    normalized = [_event_to_normalized(event) for event in raw_events]
    transformed, stats = transform(normalized)
    extra = {
        "mode": mode or os.environ.get("FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE", ""),
        "event_n": len(raw_events),
        "trigger_tokens": os.environ.get("FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS", ""),
    }
    _record_stats(stats, extra=extra)
    new_events = [
        _replace_observation_body(original, updated.body)
        if original is not None
        else original
        for original, updated in zip(raw_events, transformed)
    ]
    if hasattr(view, "model_copy"):
        return view.model_copy(update={"events": new_events})
    return view


def _event_to_normalized(event: Any):
    if hasattr(event, "model_dump"):
        payload = event.model_dump()
        if isinstance(payload, dict):
            return event_from_mapping(payload)
    if isinstance(event, dict):
        return event_from_mapping(event)
    return event_from_mapping({"source": "", "kind": type(event).__name__})


def _replace_observation_body(event: Any, new_body: str) -> Any:
    observation = getattr(event, "observation", None)
    if observation is None:
        return event
    current = _observation_text(observation)
    if current == new_body:
        return event
    updated_observation = _copy_with_text(observation, new_body)
    if hasattr(event, "model_copy"):
        return event.model_copy(update={"observation": updated_observation})
    return event


def _observation_text(observation: Any) -> str:
    content = getattr(observation, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _copy_with_text(observation: Any, new_body: str) -> Any:
    content = getattr(observation, "content", None)
    if isinstance(content, str) and hasattr(observation, "model_copy"):
        return observation.model_copy(update={"content": new_body})
    if isinstance(content, list) and content and hasattr(observation, "model_copy"):
        first = content[0]
        if hasattr(first, "model_copy"):
            new_first = first.model_copy(update={"text": new_body})
            return observation.model_copy(update={"content": [new_first]})
        if isinstance(first, dict):
            new_first = dict(first)
            new_first["text"] = new_body
            return observation.model_copy(update={"content": [new_first]})
    if hasattr(observation, "model_copy"):
        return observation.model_copy(update={"content": new_body})
    return observation


def _record_stats(stats: Any, extra: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"recorded": True}
    if hasattr(stats, "as_dict"):
        payload.update(stats.as_dict())
    elif isinstance(stats, dict):
        payload.update(stats)
    if extra:
        payload.update(extra)
    path = _audit_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except OSError:
        return


def _audit_path() -> Path | None:
    candidates = [
        os.environ.get("FEATURELIFTBENCH_AGENT_OUTPUT_DIR", "").strip(),
        "/flb/agent" if Path("/flb/agent").is_dir() else "",
    ]
    for raw in candidates:
        if raw:
            return Path(raw) / "condenser_audit.jsonl"
    return None
