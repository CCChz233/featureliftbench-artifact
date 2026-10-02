"""Conservative, model-agnostic diagnostics for Agent event trajectories."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


_READ_COMMAND = re.compile(r"\b(?:cat|sed|head|tail|less|more|rg|grep|awk|find)\b", re.I)
_TEST_COMMAND = re.compile(r"\b(?:pytest|unittest|go\s+test|python\d*\s+-m\s+pytest)\b", re.I)
_INSTALL_COMMAND = re.compile(r"\b(?:pip|uv)\s+(?:install|sync)|python\d*\s+-m\s+build", re.I)
_SUBMISSION_CHECK = re.compile(r"(?:submission-check|compare|forbidden.+import)", re.I)
_PYTHON_PROBE = re.compile(r"\b(?:python|python3|uv\s+run\s+python)\b", re.I)
_WRITE_COMMAND = re.compile(r"(?:\bcp\b|\bmv\b|\btee\b|\bmkdir\b|apply_patch|touch|\s>\s)", re.I)
_REPO_PATH = re.compile(r"(?:^|[\s'\"])(?:\.?/)?repo/([^\s'\":;,|)]+)")


def read_event_jsonl(path: str | Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_path = Path(path)
    if not event_path.is_file():
        return events
    with event_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
    return events


def audit_trajectory(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure observable policy behavior without assigning causal meaning."""

    source_reads: Counter[str] = Counter()
    commands: list[tuple[int, str]] = []
    edit_indices: list[int] = []
    verification_indices: list[int] = []
    public_verification_indices: list[int] = []
    runtime_probe_indices: list[int] = []
    system_fingerprints: list[str] = []

    for index, event in enumerate(events):
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        action_kind = str(action.get("kind") or "")
        action_command = str(action.get("command") or "")
        action_path = str(action.get("path") or "").replace("\\", "/")

        if action_kind == "FileEditorAction":
            if action_command == "view" and "/repo/" in action_path:
                source_reads[action_path.split("/repo/", 1)[1]] += 1
            if action_command in {"create", "str_replace", "insert"} and (
                "/submission/" in action_path or action_path.startswith("submission/")
            ):
                edit_indices.append(index)

        if action_kind == "TerminalAction" and action_command:
            normalized = " ".join(action_command.split())
            commands.append((index, normalized))
            if _READ_COMMAND.search(action_command):
                for match in _REPO_PATH.finditer(action_command):
                    source_reads[match.group(1)] += 1
            if ("submission/" in action_command or "/submission" in action_command) and _WRITE_COMMAND.search(
                action_command
            ):
                edit_indices.append(index)
            if (
                _TEST_COMMAND.search(action_command)
                or _INSTALL_COMMAND.search(action_command)
                or _SUBMISSION_CHECK.search(action_command)
            ):
                verification_indices.append(index)
            if _TEST_COMMAND.search(action_command) and "public" in action_command.lower():
                public_verification_indices.append(index)
            is_python_probe = bool(_PYTHON_PROBE.search(action_command)) and not re.search(
                r"py_compile|compileall|\s+-m\s+build", action_command, re.I
            )
            is_targeted_test = bool(_TEST_COMMAND.search(action_command)) and "public" not in action_command.lower()
            if is_python_probe or is_targeted_test:
                runtime_probe_indices.append(index)

        for fingerprint in _find_values(event, "system_fingerprint"):
            if fingerprint and fingerprint not in system_fingerprints:
                system_fingerprints.append(fingerprint)

    command_counts = Counter(command for _, command in commands)
    last_edit_index = max(edit_indices) if edit_indices else None
    fresh_final = bool(
        last_edit_index is not None and any(index > last_edit_index for index in verification_indices)
    )
    fresh_public = bool(
        last_edit_index is not None
        and any(index > last_edit_index for index in public_verification_indices)
    )
    return {
        "available": bool(events),
        "event_count": len(events),
        "source_read_count": sum(source_reads.values()),
        "unique_source_files_read": len(source_reads),
        "unchanged_repeated_reads": sum(count - 1 for count in source_reads.values() if count > 1),
        "repeated_read_files": sorted(path for path, count in source_reads.items() if count > 1)[:20],
        "terminal_command_count": len(commands),
        "exact_repeated_terminal_commands": sum(
            count - 1 for count in command_counts.values() if count > 1
        ),
        "runtime_probe_count": len(runtime_probe_indices),
        "last_edit_index": last_edit_index,
        "fresh_final_verification": fresh_final,
        "fresh_public_verification": fresh_public,
        "system_fingerprints": system_fingerprints,
    }


def _find_values(value: Any, key: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key and isinstance(current_value, str):
                found.append(current_value)
            else:
                found.extend(_find_values(current_value, key))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_values(item, key))
    return found
