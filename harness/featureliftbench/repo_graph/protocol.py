"""Common bounded JSON response protocol for every RSG transport."""

from __future__ import annotations

import json
from typing import Any

from .models import QUERY_SCHEMA_VERSION


def response_payload(
    *,
    command: str,
    snapshot_id: str | None,
    result: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    if max_chars < 512:
        raise ValueError("max_chars must be at least 512")
    payload: dict[str, Any] = {
        "schema_version": QUERY_SCHEMA_VERSION,
        "command": command,
        "snapshot_id": snapshot_id,
        "truncated_by_budget": False,
        "result": result,
    }
    if _size(payload) <= max_chars:
        return payload
    payload["truncated_by_budget"] = True
    _shrink(payload["result"], payload, max_chars)
    if _size(payload) > max_chars:
        payload["result"] = {
            "error": "result exceeded character budget",
            "original_keys": sorted(result),
        }
    return payload


def dumps_response(payload: dict[str, Any]) -> str:
    # Compact JSON makes the character budget equal to the bytes exposed to an Agent.
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def _shrink(result: dict[str, Any], envelope: dict[str, Any], max_chars: int) -> None:
    list_keys = [key for key, value in result.items() if isinstance(value, list)]
    original_counts = {key: len(result[key]) for key in list_keys}
    while True:
        omitted = {
            key: original_counts[key] - len(result[key])
            for key in list_keys
            if original_counts[key] != len(result[key])
        }
        if omitted:
            result["budget_omitted"] = omitted
            result["continuation_tokens"] = {
                key: f"offset:{len(result[key])}" for key in omitted
            }
        if _size(envelope) <= max_chars:
            break
        candidates = [key for key in list_keys if result[key]]
        if not candidates:
            break
        key = max(candidates, key=lambda item: _size(result[item]))
        result[key].pop()
