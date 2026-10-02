"""mini-swe-agent log parsing for suite progress."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_MINI_STEP_TOKEN_RE = re.compile(
    r"mini-swe-agent \(step (\d+), (\d+) tokens\)",
    re.IGNORECASE,
)
_MINI_STEP_COST_RE = re.compile(
    r"mini-swe-agent \(step (\d+), \$[\d.]+\)",
    re.IGNORECASE,
)
_MINI_STEP_ONLY_RE = re.compile(
    r"mini-swe-agent \(step (\d+)[,\)]",
    re.IGNORECASE,
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_RICH_TAG_RE = re.compile(r"\[[/\w]+\]")


def _shorten_str(value: str, max_len: int, *, shorten_left: bool = False) -> str:
    if not shorten_left:
        text = value[: max_len - 3] + "..." if len(value) > max_len else value
    else:
        text = "..." + value[-max_len + 3 :] if len(value) > max_len else value
    return f"{text:<{max_len}}"


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value)


def _normalize_log_text(value: str) -> str:
    return _RICH_TAG_RE.sub("", _strip_ansi(value))


def _is_noise_log_line(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned:
        return True
    if cleaned.startswith("─") or cleaned.startswith("="):
        return True
    if cleaned in {"User:", "System:", "Assistant:"}:
        return True
    return False


def parse_mini_progress_from_log(path: Path) -> str | None:
    """Extract the latest mini-swe-agent step/token status from agent stdout."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    normalized = _normalize_log_text(text)
    token_matches = list(_MINI_STEP_TOKEN_RE.finditer(normalized))
    if token_matches:
        last = token_matches[-1]
        return f"Step {last.group(1)} ({last.group(2)} toks)"

    cost_matches = list(_MINI_STEP_COST_RE.finditer(normalized))
    if cost_matches:
        last = cost_matches[-1]
        return f"Step {last.group(1)}"

    step_matches = list(_MINI_STEP_ONLY_RE.finditer(normalized))
    if step_matches:
        return f"Step {step_matches[-1].group(1)}"

    for line in reversed(text.splitlines()):
        cleaned = _normalize_log_text(line).strip()
        if _is_noise_log_line(cleaned):
            continue
        return _shorten_str(cleaned, 30)
    return None


def _int_metric(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def format_token_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 10_000:
        return f"{value // 1000}k"
    return f"{value:,}"


def parse_mini_token_total_from_trajectory(path: Path) -> int | None:
    """Sum prompt/completion tokens from mini trajectory message usage."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    prompt_tokens = 0
    completion_tokens = 0
    saw_usage = False
    for message in data.get("messages") or []:
        if not isinstance(message, dict):
            continue
        extra = message.get("extra")
        if not isinstance(extra, dict):
            continue
        response = extra.get("response")
        if not isinstance(response, dict):
            continue
        usage = response.get("usage")
        if not isinstance(usage, dict):
            continue

        prompt = _int_metric(usage.get("prompt_tokens"))
        completion = _int_metric(usage.get("completion_tokens"))
        if prompt is not None:
            prompt_tokens += prompt
            saw_usage = True
        if completion is not None:
            completion_tokens += completion
            saw_usage = True

    if not saw_usage:
        return None
    return prompt_tokens + completion_tokens


def format_mini_task_status(*, step_status: str, tokens: int | None) -> tuple[str, int | None]:
    """Combine step text from stdout with token totals from trajectory."""
    if tokens is None:
        return step_status, None
    token_text = format_token_count(tokens)
    if re.search(r"\(\d+ toks\)", step_status):
        return step_status, tokens
    if step_status.startswith("Step "):
        return f"{step_status} ({token_text} toks)", tokens
    return f"{step_status} ({token_text} toks)", tokens
