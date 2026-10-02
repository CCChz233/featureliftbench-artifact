"""Parse OpenHands JSONL event logs into FeatureLiftBench usage artifacts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTEXT_WINDOW_TOKENS = 131_072
RESERVED_OUTPUT_TOKENS = 8192
MAX_ALLOWED_PROMPT_TOKENS = CONTEXT_WINDOW_TOKENS - RESERVED_OUTPUT_TOKENS

CONTEXT_WINDOW_ENV = "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS"
RESERVED_OUTPUT_ENV = "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS"
CONDENSER_MODE_ENV = "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE"
CONDENSER_KEEP_FIRST_ENV = "FEATURELIFTBENCH_OPENHANDS_CONDENSER_KEEP_FIRST"
CONDENSER_MAX_EVENTS_ENV = "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MAX_EVENTS"
CONDENSER_ATTENTION_WINDOW_ENV = (
    "FEATURELIFTBENCH_OPENHANDS_CONDENSER_ATTENTION_WINDOW"
)

DEFAULT_CONDENSER_KEEP_FIRST = 4
DEFAULT_CONDENSER_MAX_EVENTS = 1_000_000
DEFAULT_CONDENSER_ATTENTION_WINDOW = 100

KNOWN_CONDENSER_MODES = frozenset(
    {"default", "token", "recency_masking", "artifact_aware", "verification_aware"}
)
SEEDED_CONDENSER_MODES = frozenset(
    {"token", "recency_masking", "artifact_aware", "verification_aware"}
)
CUSTOM_CONDENSER_MODES = frozenset(
    {"recency_masking", "artifact_aware", "verification_aware"}
)

DEFAULT_EVENTS_FILENAME = "openhands_events.jsonl"
DEFAULT_USAGE_FILENAME = "openhands_usage.json"
DEFAULT_STDOUT_LOG_FILENAME = "openhands_stdout.log"


@dataclass(frozen=True)
class OpenHandsProgressSnapshot:
    status: str
    event_count: int
    total_tokens: int | None


@dataclass(frozen=True)
class OpenHandsContextLimits:
    context_window_tokens: int
    reserved_output_tokens: int
    max_allowed_prompt_tokens: int


@dataclass(frozen=True)
class OpenHandsContextPolicy:
    compression_mode: str
    context_window_tokens: int
    reserved_output_tokens: int
    max_allowed_prompt_tokens: int
    condenser_trigger_tokens: int | None
    condenser_target_tokens: int | None
    condenser_keep_first: int
    condenser_max_events: int
    condenser_attention_window: int = DEFAULT_CONDENSER_ATTENTION_WINDOW

    @property
    def token_compression_enabled(self) -> bool:
        return self.compression_mode == "token"

    @property
    def requires_seeded_settings(self) -> bool:
        return self.compression_mode in SEEDED_CONDENSER_MODES


def openhands_context_limits(env: dict[str, str] | None = None) -> OpenHandsContextLimits:
    source = os.environ if env is None else env
    context_window = _positive_int_env(source, CONTEXT_WINDOW_ENV, CONTEXT_WINDOW_TOKENS)
    reserved_output = _positive_int_env(source, RESERVED_OUTPUT_ENV, RESERVED_OUTPUT_TOKENS)
    max_allowed = max(0, context_window - reserved_output)
    return OpenHandsContextLimits(
        context_window_tokens=context_window,
        reserved_output_tokens=reserved_output,
        max_allowed_prompt_tokens=max_allowed,
    )


def openhands_context_policy(env: dict[str, str] | None = None) -> OpenHandsContextPolicy:
    """Resolve the opt-in OpenHands context policy from a run environment.

    Legacy runs retain their existing OpenHands defaults. Token mode is strict:
    malformed or impossible limits raise before the first model request.
    """

    source = os.environ if env is None else env
    mode = str(source.get(CONDENSER_MODE_ENV, "default")).strip().lower() or "default"
    if mode not in KNOWN_CONDENSER_MODES:
        raise ValueError(f"unknown OpenHands condenser mode: {mode}")

    if mode in SEEDED_CONDENSER_MODES:
        context_window = _required_positive_int_env(source, CONTEXT_WINDOW_ENV)
        reserved_output = _required_positive_int_env(source, RESERVED_OUTPUT_ENV)
        if context_window <= reserved_output:
            raise ValueError(
                "OpenHands token condenser requires context_window_tokens > "
                "reserved_output_tokens"
            )
        keep_first = _non_negative_int_env(
            source,
            CONDENSER_KEEP_FIRST_ENV,
            DEFAULT_CONDENSER_KEEP_FIRST,
        )
        max_events = _required_positive_int_env(
            source,
            CONDENSER_MAX_EVENTS_ENV,
            default=DEFAULT_CONDENSER_MAX_EVENTS,
        )
        attention_window = _required_positive_int_env(
            source,
            CONDENSER_ATTENTION_WINDOW_ENV,
            default=DEFAULT_CONDENSER_ATTENTION_WINDOW,
        )
        trigger = context_window - reserved_output
        return OpenHandsContextPolicy(
            compression_mode=mode,
            context_window_tokens=context_window,
            reserved_output_tokens=reserved_output,
            max_allowed_prompt_tokens=trigger,
            condenser_trigger_tokens=trigger,
            condenser_target_tokens=trigger // 2,
            condenser_keep_first=keep_first,
            condenser_max_events=max_events,
            condenser_attention_window=attention_window,
        )

    limits = openhands_context_limits(source)
    return OpenHandsContextPolicy(
        compression_mode=mode,
        context_window_tokens=limits.context_window_tokens,
        reserved_output_tokens=limits.reserved_output_tokens,
        max_allowed_prompt_tokens=limits.max_allowed_prompt_tokens,
        condenser_trigger_tokens=None,
        condenser_target_tokens=None,
        condenser_keep_first=DEFAULT_CONDENSER_KEEP_FIRST,
        condenser_max_events=DEFAULT_CONDENSER_MAX_EVENTS,
    )


def context_policy_audit_fields(
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    policy = openhands_context_policy(env)
    return {
        "compression_mode": policy.compression_mode,
        "context_window_tokens": policy.context_window_tokens,
        "reserved_output_tokens": policy.reserved_output_tokens,
        "max_allowed_prompt_tokens": policy.max_allowed_prompt_tokens,
        "condenser_trigger_tokens": policy.condenser_trigger_tokens,
        "condenser_target_tokens": policy.condenser_target_tokens,
        "condenser_keep_first": policy.condenser_keep_first,
        "condenser_max_events": policy.condenser_max_events,
        "condenser_attention_window": policy.condenser_attention_window,
    }


def parse_openhands_progress_snapshot(log_path: Path) -> OpenHandsProgressSnapshot | None:
    """Extract live suite progress from an OpenHands JSONL stdout log."""
    if not log_path.is_file():
        return None

    event_count = 0
    total_tokens = 0
    saw_tokens = False
    last_label = ""
    try:
        events = _iter_json_events(log_path)
        for event in events:
            event_count += 1
            last_label = _openhands_event_label(event)
            for usage in _iter_usage_records(event):
                prompt = _int_metric(usage.get("prompt_tokens"))
                completion = _int_metric(usage.get("completion_tokens"))
                total = _int_metric(usage.get("total_tokens"))
                if prompt is not None:
                    total_tokens += prompt
                    saw_tokens = True
                if completion is not None:
                    total_tokens += completion
                    saw_tokens = True
                if total is not None and prompt is None and completion is None:
                    total_tokens += total
                    saw_tokens = True
    except OSError:
        return None

    if event_count <= 0:
        return None
    label = last_label or "agent"
    return OpenHandsProgressSnapshot(
        status=f"Event {event_count} · {label}",
        event_count=event_count,
        total_tokens=total_tokens if saw_tokens else None,
    )


def _openhands_event_label(event: dict[str, Any]) -> str:
    source = str(event.get("source") or "").strip()
    if source == "environment":
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            return tool_name
    if source == "agent":
        action = event.get("action")
        if isinstance(action, dict):
            command = action.get("command")
            if isinstance(command, str) and command.strip():
                return command.strip().split()[0]
    if source:
        return source
    event_type = str(event.get("type") or event.get("event") or "").strip()
    return event_type or "event"


def resolve_events_path(
    agent_output_dir: Path,
    *,
    stdout_log: Path | None = None,
) -> Path | None:
    """Pick the best JSONL source: dedicated events file, then stdout capture."""
    events_path = agent_output_dir / DEFAULT_EVENTS_FILENAME
    if events_path.is_file() and events_path.stat().st_size > 0:
        return events_path
    stdout_path = stdout_log or (agent_output_dir / DEFAULT_STDOUT_LOG_FILENAME)
    if stdout_path.is_file() and stdout_path.stat().st_size > 0:
        return stdout_path
    return None


def parse_events_jsonl(path: Path) -> dict[str, Any]:
    """Aggregate token usage from an OpenHands --json JSONL file."""
    limits = openhands_context_limits()
    if not path.is_file():
        return _empty_usage(unverified=True, reason="events_file_missing", limits=limits)

    prompt_tokens = 0
    completion_tokens = 0
    api_calls = 0
    assistant_steps = 0
    max_prompt_tokens_per_call = 0
    max_total_tokens_per_call = 0
    saw_usage = False
    compression = {
        "condensation_events": 0,
        "forgotten_event_count": 0,
        "condensation_summaries_nonempty": 0,
    }

    try:
        events = _iter_json_events(path)
        for event in events:
            _accumulate_condensation_event(event, compression)
            for usage in _iter_usage_records(event):
                saw_usage = True
                prompt = _int_metric(usage.get("prompt_tokens"))
                completion = _int_metric(usage.get("completion_tokens"))
                total = _int_metric(usage.get("total_tokens"))
                if prompt is not None:
                    prompt_tokens += prompt
                    max_prompt_tokens_per_call = max(max_prompt_tokens_per_call, prompt)
                if completion is not None:
                    completion_tokens += completion
                if total is not None:
                    max_total_tokens_per_call = max(max_total_tokens_per_call, total)
                elif prompt is not None or completion is not None:
                    call_total = (prompt or 0) + (completion or 0)
                    max_total_tokens_per_call = max(max_total_tokens_per_call, call_total)
                api_calls += 1

            if _looks_like_assistant_step(event):
                assistant_steps += 1
    except OSError:
        return _empty_usage(unverified=True, reason="events_file_unreadable", limits=limits)

    if not saw_usage:
        return _empty_usage(unverified=True, reason="no_usage_in_events", limits=limits)

    if max_prompt_tokens_per_call == 0 and prompt_tokens > 0:
        max_prompt_tokens_per_call = prompt_tokens
    if max_total_tokens_per_call == 0:
        max_total_tokens_per_call = prompt_tokens + completion_tokens

    context_violation = max_prompt_tokens_per_call > limits.max_allowed_prompt_tokens
    return {
        "assistant_steps": assistant_steps,
        "api_calls": api_calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "context_audit": {
            "available": True,
            "runtime": "openhands",
            "history_policy": "external_openhands",
            "token_source": "openhands_jsonl",
            "usage_unverified": False,
            "context_window_tokens": limits.context_window_tokens,
            "reserved_output_tokens": limits.reserved_output_tokens,
            "max_allowed_prompt_tokens": limits.max_allowed_prompt_tokens,
            "max_prompt_tokens_per_call": max_prompt_tokens_per_call,
            "max_total_tokens_per_call": max_total_tokens_per_call,
            "context_violation": context_violation,
            "over_context_behavior": "managed_by_openhands",
            **context_policy_audit_fields(),
            **compression,
        },
    }


def parse_openhands_compression_events(path: Path | None) -> dict[str, int]:
    """Count condensation events without retaining summary text or event IDs."""

    counts = {
        "condensation_events": 0,
        "forgotten_event_count": 0,
        "condensation_summaries_nonempty": 0,
    }
    if path is None or not path.is_file():
        return counts
    try:
        for event in _iter_json_events(path):
            _accumulate_condensation_event(event, counts)
    except OSError:
        return counts
    return counts


def write_usage_from_events(
    events_path: Path,
    output_path: Path,
) -> dict[str, Any] | None:
    """Parse JSONL and write ``openhands_usage.json`` when usage is found."""
    usage = parse_events_jsonl(events_path)
    context_audit = usage.get("context_audit")
    if not isinstance(context_audit, dict):
        return None
    if context_audit.get("usage_unverified"):
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(usage, indent=2, sort_keys=True), encoding="utf-8")
    return usage


def _empty_usage(
    *,
    unverified: bool,
    reason: str,
    limits: OpenHandsContextLimits | None = None,
) -> dict[str, Any]:
    limits = limits or openhands_context_limits()
    return {
        "assistant_steps": 0,
        "api_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "context_audit": {
            "available": False,
            "runtime": "openhands",
            "history_policy": "external_openhands",
            "token_source": reason,
            "usage_unverified": unverified,
            "context_window_tokens": limits.context_window_tokens,
            "reserved_output_tokens": limits.reserved_output_tokens,
            "max_allowed_prompt_tokens": limits.max_allowed_prompt_tokens,
            "over_context_behavior": "managed_by_openhands",
            **context_policy_audit_fields(),
            "condensation_events": 0,
            "forgotten_event_count": 0,
            "condensation_summaries_nonempty": 0,
        },
    }


def _positive_int_env(source: dict[str, str], name: str, default: int) -> int:
    raw = source.get(name)
    if raw is None:
        return default
    try:
        parsed = int(str(raw).strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _required_positive_int_env(
    source: dict[str, str],
    name: str,
    *,
    default: int | None = None,
) -> int:
    raw = source.get(name)
    if raw is None and default is not None:
        return default
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _non_negative_int_env(
    source: dict[str, str],
    name: str,
    default: int,
) -> int:
    raw = source.get(name, str(default))
    try:
        parsed = int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def _accumulate_condensation_event(
    event: dict[str, Any],
    counts: dict[str, int],
) -> None:
    kind = str(event.get("kind") or event.get("type") or "")
    if kind != "Condensation":
        return
    counts["condensation_events"] += 1
    forgotten = event.get("forgotten_event_ids")
    if isinstance(forgotten, list):
        counts["forgotten_event_count"] += len(forgotten)
    summary = event.get("summary")
    if isinstance(summary, str) and summary.strip():
        counts["condensation_summaries_nonempty"] += 1


def _iter_json_events(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or not stripped.startswith("{"):
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event


def _iter_usage_records(event: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key in ("usage", "token_usage", "metrics"):
        nested = event.get(key)
        if isinstance(nested, dict) and _has_token_fields(nested):
            records.append(nested)
    message = event.get("message")
    if isinstance(message, dict):
        nested = message.get("usage")
        if isinstance(nested, dict) and _has_token_fields(nested):
            records.append(nested)
    llm_metrics = event.get("llm_metrics")
    if isinstance(llm_metrics, dict):
        for value in llm_metrics.values():
            if isinstance(value, dict) and _has_token_fields(value):
                records.append(value)
    data = event.get("data")
    if isinstance(data, dict):
        nested = data.get("usage")
        if isinstance(nested, dict) and _has_token_fields(nested):
            records.append(nested)
    return records


def _has_token_fields(record: dict[str, Any]) -> bool:
    return any(
        _int_metric(record.get(key)) is not None
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    )


def _looks_like_assistant_step(event: dict[str, Any]) -> bool:
    event_type = str(event.get("type") or event.get("event") or "").lower()
    source = str(event.get("source") or "").lower()
    role = str(event.get("role") or "").lower()
    if role == "assistant":
        return True
    if source == "agent" and isinstance(event.get("action"), dict):
        return True
    return any(marker in event_type for marker in ("assistant", "agent", "action", "message"))


def looks_like_openhands_step(event: dict[str, Any]) -> bool:
    """Return whether an OpenHands JSON event should count as an agent step."""

    return _looks_like_assistant_step(event)


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
