"""Parse OpenHands events and pair actions with observations by stable IDs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .constants import EDITOR_WRITE_COMMANDS
from .util import iter_jsonl, parse_ts


def normalize_tool(name: str | None) -> str:
    text = str(name or "")
    if "<|" in text:
        text = text.split("<|", 1)[0]
    text = text.strip()
    if text in {"bash", "execute_bash", "run_terminal_cmd"}:
        return "terminal"
    return text


def observation_text(observation: dict[str, Any]) -> str:
    content = observation.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(content, str):
        return content
    return ""


@dataclass
class EventRecord:
    index: int
    event_id: str
    kind: str
    timestamp: float | None
    tool_name: str
    tool_call_id: str
    action_id: str
    llm_response_id: str
    payload: dict[str, Any]


@dataclass
class ToolCompletion:
    event_index: int
    event_id: str
    action_event_id: str
    tool_call_id: str
    llm_response_id: str
    tool_name: str
    timestamp: float | None
    command: str
    path: str
    is_error: bool
    mutation_kind: str
    editor_command: str
    new_content: str | None
    observation: dict[str, Any]
    unmatched: bool = False


def load_events(path: Path) -> list[EventRecord]:
    records: list[EventRecord] = []
    for index, payload in enumerate(iter_jsonl(path)):
        kind = str(payload.get("kind") or payload.get("type") or "")
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        tool_call = payload.get("tool_call") if isinstance(payload.get("tool_call"), dict) else {}
        tool_call_id = str(
            payload.get("tool_call_id")
            or tool_call.get("id")
            or ""
        )
        action_id = str(payload.get("action_id") or payload.get("id") or "")
        records.append(
            EventRecord(
                index=index,
                event_id=str(payload.get("id") or f"event-{index}"),
                kind=kind,
                timestamp=parse_ts(payload.get("timestamp")),
                tool_name=normalize_tool(payload.get("tool_name") or action.get("kind")),
                tool_call_id=tool_call_id,
                action_id=str(payload.get("id") or "") if kind == "ActionEvent" else str(payload.get("action_id") or ""),
                llm_response_id=str(payload.get("llm_response_id") or ""),
                payload=payload,
            )
        )
    return records


def load_persistence_events(persistence_dir: Path) -> list[EventRecord]:
    events_root = persistence_dir / "conversations"
    if not events_root.is_dir():
        return []
    paths: list[Path] = []
    for conv in events_root.iterdir():
        folder = conv / "events"
        if folder.is_dir():
            paths.extend(sorted(folder.glob("event-*.json")))
    rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda item: (str(item.get("timestamp") or ""), str(item.get("id") or "")))
    records: list[EventRecord] = []
    for index, payload in enumerate(rows):
        records.append(
            EventRecord(
                index=index,
                event_id=str(payload.get("id") or path_stem(paths, index)),
                kind=str(payload.get("kind") or ""),
                timestamp=parse_ts(payload.get("timestamp")),
                tool_name=normalize_tool(payload.get("tool_name")),
                tool_call_id=str(payload.get("tool_call_id") or ""),
                action_id=str(payload.get("id") if payload.get("kind") == "ActionEvent" else payload.get("action_id") or ""),
                llm_response_id=str(payload.get("llm_response_id") or ""),
                payload=payload,
            )
        )
    return records


def path_stem(paths: list[Path], index: int) -> str:
    if 0 <= index < len(paths):
        return paths[index].stem
    return f"persistence-{index}"


def pair_completions(events: list[EventRecord]) -> tuple[list[ToolCompletion], dict[str, int]]:
    pending_by_call: dict[str, EventRecord] = {}
    pending_by_action: dict[str, EventRecord] = {}
    unmatched_obs = 0
    unmatched_actions = 0
    completions: list[ToolCompletion] = []
    for event in events:
        if event.kind == "ActionEvent":
            if event.tool_call_id:
                pending_by_call[event.tool_call_id] = event
            if event.event_id:
                pending_by_action[event.event_id] = event
            continue
        if event.kind != "ObservationEvent":
            continue
        action = None
        if event.tool_call_id and event.tool_call_id in pending_by_call:
            action = pending_by_call.pop(event.tool_call_id)
            pending_by_action.pop(action.event_id, None)
        elif event.action_id and event.action_id in pending_by_action:
            action = pending_by_action.pop(event.action_id)
            pending_by_call.pop(action.tool_call_id, None)
        observation = event.payload.get("observation")
        if not isinstance(observation, dict):
            observation = {}
        action_payload = action.payload.get("action") if action and isinstance(action.payload.get("action"), dict) else {}
        command = str(observation.get("command") or action_payload.get("command") or "")
        path = str(observation.get("path") or action_payload.get("path") or "")
        editor_command = str(observation.get("command") or action_payload.get("command") or "")
        new_content = observation.get("new_content")
        if not isinstance(new_content, str):
            new_content = None
        is_error = bool(observation.get("is_error"))
        tool_name = normalize_tool(event.tool_name or (action.tool_name if action else ""))
        completions.append(
            ToolCompletion(
                event_index=event.index,
                event_id=event.event_id,
                action_event_id=action.event_id if action else "",
                tool_call_id=event.tool_call_id or (action.tool_call_id if action else ""),
                llm_response_id=(action.llm_response_id if action else event.llm_response_id),
                tool_name=tool_name,
                timestamp=event.timestamp if event.timestamp is not None else (action.timestamp if action else None),
                command=command,
                path=path,
                is_error=is_error,
                mutation_kind=classify_mutation(tool_name, editor_command, command, path, is_error, new_content),
                editor_command=editor_command if tool_name == "file_editor" else "",
                new_content=new_content,
                observation=observation,
                unmatched=action is None,
            )
        )
        if action is None:
            unmatched_obs += 1
    unmatched_actions = len(pending_by_call)
    stats = {
        "unmatched_observations": unmatched_obs,
        "unmatched_actions": unmatched_actions,
        "completions": len(completions),
    }
    return completions, stats


def classify_mutation(
    tool_name: str,
    editor_command: str,
    command: str,
    path: str,
    is_error: bool,
    new_content: str | None,
) -> str:
    if tool_name == "file_editor":
        if editor_command in {"view"}:
            return "none"
        if is_error:
            return "editor_failed"
        if editor_command in EDITOR_WRITE_COMMANDS and new_content is not None:
            return "editor_write"
        if editor_command in {"rename", "mv"}:
            return "rename"
        if editor_command in {"delete", "rm"}:
            return "delete"
        return "editor_unknown"
    if tool_name == "terminal":
        if is_error:
            return "terminal_error"
        return classify_terminal_command(command)
    return "none"


def classify_terminal_command(command: str) -> str:
    compact = " ".join(command.strip().split())
    if not compact:
        return "none"
    if _inspection_only(compact):
        return "none"
    if _pytest_only(compact):
        return "none"
    kinds: list[str] = []
    if _has_token(compact, ("ln", "symlink")):
        kinds.append("symlink")
    if _has_token(compact, ("mv", "rename")):
        kinds.append("rename")
    if _has_token(compact, ("rm", "unlink", "rmdir")):
        kinds.append("delete")
    if "featurelifted" in compact.replace("\\", "/") or "submission/" in compact.replace("\\", "/"):
        kinds.append("terminal_write")
    if kinds:
        if len(kinds) == 1:
            return kinds[0]
        return "terminal_mixed"
    if _looks_mutating(compact):
        return "terminal_write"
    return "none"


def _has_token(command: str, tokens: tuple[str, ...]) -> bool:
    import re

    return any(re.search(rf"(^|[;&|]\s*){token}\b", command) for token in tokens)


def _looks_mutating(command: str) -> bool:
    import re

    return bool(
        re.search(
            r"""
            \b(cp|mv|rm|mkdir|touch|install|rsync|ln|chmod|chown)\b
            |sed\s+-i
            |\btee\b
            |>>
            |cat\s*>
            """,
            command,
            re.VERBOSE,
        )
    )


def _pytest_only(command: str) -> bool:
    import re

    if not re.search(r"\bpytest\b|\bpython3?\s+-m\s+pytest\b", command):
        return False
    return not _looks_mutating(command)


def _inspection_only(command: str) -> bool:
    import re

    compact = " ".join(command.strip().split())
    if _looks_mutating(compact):
        return False
    return bool(re.search(r"^\s*(ls|head|tail|grep|rg|find|wc|sed\s+-n|nl|file|stat|tree|du|cat|pwd|which|echo)\b", compact))


def count_event_kinds(events: list[EventRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        key = event.kind or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def count_tools(completions: list[ToolCompletion]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in completions:
        counts[item.tool_name or "unknown"] = counts.get(item.tool_name or "unknown", 0) + 1
    return counts


def original_steps(events: list[EventRecord]) -> int:
    return sum(1 for event in events if event.kind == "ActionEvent")


def iter_llm_response_order(events: list[EventRecord]) -> Iterator[str]:
    seen: set[str] = set()
    for event in events:
        response_id = event.llm_response_id
        if not response_id or response_id in seen:
            continue
        if event.kind in {"ActionEvent", "MessageEvent"}:
            seen.add(response_id)
            yield response_id
