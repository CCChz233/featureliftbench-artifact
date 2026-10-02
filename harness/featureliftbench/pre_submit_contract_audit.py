"""Parse pre-submit explicit-contract audit process metrics from trajectories."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from typing import Mapping


AUDIT_HEADER = "PRE-SUBMIT CONTRACT AUDIT"


def task_appendix() -> str:
    """Force a public-spec checklist without inventing Hidden contracts."""

    return (
        "## Pre-submit Explicit-Contract Audit\n\n"
        "Before you finish, walk the public Required Output API and every `Bxxx` "
        "clause already written in TASK.md against files in `submission/`.\n\n"
        "Do not invent a new contract. Do not guess Hidden tests. Do not search "
        "for evaluator tests or public test files. There is no `flb-contract-check` "
        "tool and no repair round in this arm.\n\n"
        "Write the checklist in this exact format. If you find a gap you can close "
        "from the public spec, keep editing `submission/`; otherwise finish:\n\n"
        "PRE-SUBMIT CONTRACT AUDIT\n"
        "- B001: covered\n"
        "- required API: gap missing export\n"
        "AUDIT_RESULT: gaps\n"
    )


def openhands_appendix() -> str:
    """Mirror the explicit-contract checklist in the OpenHands wrapper prompt."""

    return (
        "Before finishing, walk the public Required Output API and every Bxxx "
        "clause already in TASK.md against `submission/`. Do not invent new "
        "contracts, guess Hidden tests, or hunt evaluator tests. There is no "
        "flb-contract-check and no repair round. Emit this exact block:\n"
        "PRE-SUBMIT CONTRACT AUDIT\n"
        "- B001: covered|gap ...\n"
        "AUDIT_RESULT: gaps|complete\n"
    )


AUDIT_RESULT_RE = re.compile(
    r"AUDIT_RESULT:\s*(gaps|complete|gap)\b",
    re.IGNORECASE,
)
GAP_LINE_RE = re.compile(
    r"^\s*[-*]\s*(B\d+|required\s+api)[^\n]*(gap|missing|uncovered)\b",
    re.IGNORECASE | re.MULTILINE,
)
COVERED_LINE_RE = re.compile(
    r"^\s*[-*]\s*(B\d+)[^\n]*(covered|ok|done)\b",
    re.IGNORECASE | re.MULTILINE,
)


def parse_pre_submit_audit(
    events: list[Mapping[str, Any]] | Path,
) -> dict[str, Any]:
    """Detect whether the agent executed the explicit-contract checklist."""

    records = _load_events(events)
    texts = [_event_text(event) for event in records]
    combined = "\n".join(text for text in texts if text)
    executed = AUDIT_HEADER.lower() in combined.lower() or bool(
        AUDIT_RESULT_RE.search(combined)
    )
    result_match = AUDIT_RESULT_RE.search(combined)
    result = result_match.group(1).lower() if result_match else ""
    gap_found = result in {"gaps", "gap"} or bool(GAP_LINE_RE.search(combined))
    if not executed:
        return {
            "audit_executed": False if combined.strip() else "unknown",
            "explicit_gap_found": "unknown",
            "continued_after_gap": "unknown",
            "audit_result": "",
        }

    continued = False
    if gap_found:
        header_index = _first_index_containing(texts, AUDIT_HEADER)
        if header_index < 0:
            header_index = _first_index_containing(texts, "AUDIT_RESULT:")
        continued = _has_submission_edit_after(records, header_index)

    return {
        "audit_executed": True,
        "explicit_gap_found": gap_found,
        "continued_after_gap": continued if gap_found else False,
        "audit_result": "gaps" if gap_found else (result or "complete"),
        "checklist_lines": len(COVERED_LINE_RE.findall(combined))
        + len(GAP_LINE_RE.findall(combined)),
    }


def write_pre_submit_audit(
    events_path: Path,
    output_path: Path,
    *,
    public_pass: bool | None = None,
) -> dict[str, Any]:
    payload = parse_pre_submit_audit(events_path)
    if public_pass is not None:
        payload["public_pass"] = public_pass
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return payload


def _load_events(events: list[Mapping[str, Any]] | Path) -> list[Mapping[str, Any]]:
    if isinstance(events, Path):
        records: list[Mapping[str, Any]] = []
        if not events.is_file():
            return records
        for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records
    return list(events)


def _event_text(event: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("thought", "reasoning_content", "content", "message"):
        value = event.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
    action = event.get("action")
    if isinstance(action, dict):
        command = action.get("command")
        if isinstance(command, str):
            parts.append(command)
    observation = event.get("observation")
    if isinstance(observation, dict):
        content = observation.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
    message = event.get("llm_message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
    return "\n".join(parts)


def _first_index_containing(texts: list[str], marker: str) -> int:
    needle = marker.lower()
    for index, text in enumerate(texts):
        if needle in text.lower():
            return index
    return -1


def _has_submission_edit_after(events: list[Mapping[str, Any]], start: int) -> bool:
    if start < 0:
        return False
    for event in events[start + 1 :]:
        kind = str(event.get("kind") or "")
        tool_name = str(event.get("tool_name") or "")
        if "edit" in kind.lower() or tool_name in {
            "file_editor",
            "str_replace_editor",
            "edit_file",
        }:
            return True
        action = event.get("action")
        command = ""
        if isinstance(action, dict):
            raw = action.get("command")
            if isinstance(raw, str):
                command = raw
            path = action.get("path")
            if isinstance(path, str) and "submission" in path.replace("\\", "/"):
                return True
        lowered = command.replace("\\", "/").lower()
        if "submission/" in lowered and any(
            token in lowered for token in (">", "tee", "cp ", "mv ")
        ):
            return True
    return False
