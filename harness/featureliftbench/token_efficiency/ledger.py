"""Per-call token ledgers with duplicate removal and bounded alignment."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .constants import ACCOUNTING_MAIN_TABLE, ACCOUNTING_TOTAL
from .events import EventRecord, ToolCompletion, iter_llm_response_order
from .util import as_int, iter_jsonl, parse_ts, read_json, sha256_bytes


@dataclass
class CallRecord:
    call_id: str
    request_id: str
    response_id: str
    event_ids: list[str]
    started_at: str
    ended_at: str
    timestamp: float | None
    model: str
    status: str
    usage_source: str
    usage_verified: bool | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    prompt_cache_hit_tokens: int | None
    prompt_cache_miss_tokens: int | None
    prompt_cache_accounting_available: bool | None
    accounting_basis: str
    main_table_tokens: int | None
    duplicate_of: str
    inclusion_status: str
    missing_reason: str
    model_role: str = "primary"
    line_index: int = 0

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_ids"] = ",".join(self.event_ids)
        payload["cache_fields"] = {
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "prompt_cache_accounting_available": self.prompt_cache_accounting_available,
        }
        return payload


@dataclass
class RunLedger:
    calls: list[CallRecord]
    accounting_basis: str
    token_usage_status: str
    token_alignment_status: str
    total_tokens: int | None
    main_table_tokens: int | None
    usage_json_total: int | None
    ledger_minus_usage: int | None
    missing_reason: str = ""
    notes: str = ""
    response_to_call: dict[str, str] = field(default_factory=dict)
    cumulative_by_call: dict[str, int] = field(default_factory=dict)
    cumulative_bounds_by_call: dict[str, tuple[int, int]] = field(default_factory=dict)


def fingerprint_call(payload: dict[str, Any], timestamp: str, tokens: tuple[Any, Any, Any]) -> str:
    blob = "|".join(
        [
            timestamp,
            str(payload.get("model") or ""),
            str(payload.get("path") or ""),
            str(payload.get("target_url") or ""),
            str(tokens[0]),
            str(tokens[1]),
            str(tokens[2]),
            str(payload.get("status") or ""),
        ]
    )
    return sha256_bytes(blob.encode("utf-8"))[:16]


def load_audit_calls(audit_path: Path) -> list[CallRecord]:
    if not audit_path.is_file():
        return []
    records: list[CallRecord] = []
    seen: dict[str, str] = {}
    for index, payload in enumerate(iter_jsonl(audit_path)):
        timestamp = str(payload.get("timestamp") or "")
        prompt = as_int(payload.get("prompt_tokens"))
        completion = as_int(payload.get("completion_tokens"))
        total = as_int(payload.get("total_tokens"))
        if total is None and prompt is not None and completion is not None:
            total = prompt + completion
        fingerprint = fingerprint_call(payload, timestamp, (prompt, completion, total))
        duplicate_of = seen.get(fingerprint, "")
        inclusion = "duplicate" if duplicate_of else "included"
        if not duplicate_of:
            seen[fingerprint] = f"call-{index}"
        missing = ""
        if prompt is None and completion is None and total is None:
            missing = "audit_tokens_null"
            inclusion = "excluded_missing_usage" if not duplicate_of else inclusion
        cache_available = payload.get("prompt_cache_accounting_available")
        main_table = None
        if cache_available is True:
            miss = as_int(payload.get("prompt_cache_miss_tokens"))
            if miss is not None and completion is not None:
                main_table = miss + completion
        elif total is not None:
            main_table = total
        records.append(
            CallRecord(
                call_id=f"call-{index}",
                request_id=str(payload.get("request_id") or payload.get("id") or ""),
                response_id=str(payload.get("response_id") or ""),
                event_ids=[],
                started_at=timestamp,
                ended_at=timestamp,
                timestamp=parse_ts(timestamp),
                model=str(payload.get("model") or ""),
                status=str(payload.get("status") or ""),
                usage_source="context_audit.jsonl",
                usage_verified=_optional_bool(payload.get("usage_verified")),
                input_tokens=prompt,
                output_tokens=completion,
                total_tokens=total,
                prompt_cache_hit_tokens=as_int(payload.get("prompt_cache_hit_tokens")),
                prompt_cache_miss_tokens=as_int(payload.get("prompt_cache_miss_tokens")),
                prompt_cache_accounting_available=_optional_bool(cache_available),
                accounting_basis=ACCOUNTING_TOTAL,
                main_table_tokens=main_table,
                duplicate_of=duplicate_of,
                inclusion_status=inclusion,
                missing_reason=missing,
                line_index=index,
            )
        )
    return records


def load_usage_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = read_json(path)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_run_ledger(
    *,
    configuration: str,
    audit_path: Path,
    usage_path: Path,
    events: list[EventRecord],
) -> RunLedger:
    calls = load_audit_calls(audit_path)
    usage = load_usage_json(usage_path)
    included = [call for call in calls if call.inclusion_status == "included"]
    has_complete = [call for call in included if call.total_tokens is not None]
    usage_total = as_int(usage.get("total_tokens"))
    if usage_total == 0 and usage.get("context_audit", {}).get("usage_unverified") is True:
        usage_total = None
    if usage.get("available") is False:
        usage_total = None

    token_usage_status = "missing"
    missing_reason = ""
    missing_calls = [call for call in calls if call.inclusion_status == "excluded_missing_usage"]
    if has_complete and missing_calls:
        token_usage_status = "partial"
        missing_reason = "some_calls_missing_usage"
    elif has_complete and len(has_complete) == len(included) and included:
        token_usage_status = "complete"
    elif has_complete:
        token_usage_status = "partial"
        missing_reason = "some_calls_missing_usage"
    elif included:
        token_usage_status = "missing"
        missing_reason = "per_call_usage_null"
    elif any(call.inclusion_status == "excluded_missing_usage" for call in calls):
        token_usage_status = "missing"
        missing_reason = "per_call_usage_null"
    elif not calls:
        token_usage_status = "missing"
        missing_reason = "no_context_audit"
    else:
        token_usage_status = "missing"
        missing_reason = "all_calls_duplicates_or_null"

    total_tokens = sum(call.total_tokens or 0 for call in has_complete) if has_complete and token_usage_status == "complete" else None
    main_table_tokens = None
    if token_usage_status == "complete" and all(call.main_table_tokens is not None for call in included):
        main_table_tokens = sum(call.main_table_tokens or 0 for call in included)

    if configuration in {"deepseek-v4-pro", "deepseek-v4-flash"}:
        accounting_note = "main_table=uncached_prompt+completion"
    else:
        accounting_note = "main_table=provider_total"

    ledger_minus_usage = None
    if total_tokens is not None and usage_total is not None:
        ledger_minus_usage = total_tokens - usage_total

    alignment_status, response_map, notes = align_calls_to_responses(included, events)
    cumulative, bounds = _cumulative_maps(included)

    if token_usage_status != "complete":
        if alignment_status == "exact":
            alignment_status = "usage_missing"
        total_tokens = None
        main_table_tokens = None

    return RunLedger(
        calls=calls,
        accounting_basis=ACCOUNTING_TOTAL,
        token_usage_status=token_usage_status,
        token_alignment_status=alignment_status,
        total_tokens=total_tokens,
        main_table_tokens=main_table_tokens,
        usage_json_total=usage_total,
        ledger_minus_usage=ledger_minus_usage,
        missing_reason=missing_reason,
        notes="; ".join(item for item in [accounting_note, notes] if item),
        response_to_call=response_map,
        cumulative_by_call=cumulative,
        cumulative_bounds_by_call=bounds,
    )


def align_calls_to_responses(
    calls: list[CallRecord],
    events: list[EventRecord],
) -> tuple[str, dict[str, str], str]:
    response_ids = list(iter_llm_response_order(events))
    usable = [call for call in calls if call.inclusion_status == "included"]
    if not usable and not response_ids:
        return "empty", {}, ""
    if not usable:
        return "unresolved", {}, "no_included_calls"
    # Prefer request/response IDs when present.
    if all(call.response_id for call in usable) and set(call.response_id for call in usable) <= set(response_ids):
        mapping = {call.response_id: call.call_id for call in usable}
        return "exact", mapping, "aligned_by_response_id"
    if len(usable) == len(response_ids):
        mapping = {response_ids[index]: usable[index].call_id for index in range(len(usable))}
        if _timestamps_compatible(usable, events, mapping):
            return "exact", mapping, "aligned_by_order"
        return "bounded", mapping, "order_aligned_timestamp_ambiguous"
    mapping = _greedy_time_match(usable, events, response_ids)
    if len(mapping) == min(len(usable), len(response_ids)) and mapping:
        return "bounded", mapping, "greedy_time_match_count_mismatch"
    return "unresolved", mapping, f"call_n={len(usable)} response_n={len(response_ids)}"


def _event_time_for_response(events: list[EventRecord], response_id: str) -> float | None:
    for event in events:
        if event.llm_response_id == response_id and event.timestamp is not None:
            return event.timestamp
    return None


def _timestamps_compatible(
    calls: list[CallRecord],
    events: list[EventRecord],
    mapping: dict[str, str],
) -> bool:
    by_id = {call.call_id: call for call in calls}
    for response_id, call_id in mapping.items():
        call = by_id[call_id]
        event_ts = _event_time_for_response(events, response_id)
        if call.timestamp is None or event_ts is None:
            return False
        if call.timestamp - 2.0 > event_ts:
            return False
    return True


def _greedy_time_match(
    calls: list[CallRecord],
    events: list[EventRecord],
    response_ids: list[str],
) -> dict[str, str]:
    remaining = list(calls)
    mapping: dict[str, str] = {}
    for response_id in response_ids:
        event_ts = _event_time_for_response(events, response_id)
        if event_ts is None or not remaining:
            continue
        ranked = sorted(
            remaining,
            key=lambda call: (
                abs((call.timestamp or event_ts) - event_ts),
                call.line_index,
            ),
        )
        chosen = ranked[0]
        if chosen.timestamp is not None and abs(chosen.timestamp - event_ts) > 30:
            continue
        mapping[response_id] = chosen.call_id
        remaining.remove(chosen)
    return mapping


def _cumulative_maps(calls: list[CallRecord]) -> tuple[dict[str, int], dict[str, tuple[int, int]]]:
    exact: dict[str, int] = {}
    bounds: dict[str, tuple[int, int]] = {}
    running = 0
    running_upper = 0
    for call in calls:
        if call.inclusion_status != "included":
            continue
        if call.total_tokens is None:
            running_upper = running_upper
            bounds[call.call_id] = (running, running_upper)
            continue
        running += call.total_tokens
        running_upper = running
        exact[call.call_id] = running
        bounds[call.call_id] = (running, running)
    return exact, bounds


def tokens_for_completion(
    ledger: RunLedger,
    completion: ToolCompletion,
    seen_responses: set[str],
) -> tuple[int | None, int | None, int | None, str]:
    """Return (exact, lower, upper, status) cumulative tokens after this tool completes.

    A response's full usage is attributed at its first tool completion and not
    re-added for later tools from the same response.
    """

    if ledger.token_usage_status != "complete":
        return None, None, None, "usage_missing"
    response_id = completion.llm_response_id
    if not response_id:
        return None, None, None, "unresolved"
    call_id = ledger.response_to_call.get(response_id)
    if not call_id:
        return None, None, None, ledger.token_alignment_status
    if ledger.token_alignment_status == "unresolved":
        return None, None, None, "unresolved"
    exact = ledger.cumulative_by_call.get(call_id)
    bounds = ledger.cumulative_bounds_by_call.get(call_id)
    if ledger.token_alignment_status == "exact" and exact is not None:
        return exact, exact, exact, "exact"
    # A precise sum for a candidate call does not make its event mapping exact.
    # Without a proven mapping, the candidate prefix is not a valid tight bound.
    if ledger.token_alignment_status == "bounded":
        return None, 0, ledger.total_tokens, "bounded"
    return None, None, None, "unresolved"


def call_usage_available(ledger: RunLedger) -> bool:
    return ledger.token_usage_status == "complete"


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
    return None
