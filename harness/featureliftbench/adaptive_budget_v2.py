"""V2 Adaptive Budget: 1.5M Main primary + one progress checkpoint + optional 500K targeted repair.

Legal signals only (events / submission mtime). Never uses evaluator public/hidden tests
or contract-closure checkers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ADAPTIVE_BUDGET_V2_ENV = "FEATURELIFTBENCH_ADAPTIVE_BUDGET_V2"
ADAPTIVE_BUDGET_V2_PHASE_ENV = "FEATURELIFTBENCH_ADAPTIVE_BUDGET_V2_PHASE"
CHECKPOINT_FILE = "v2_checkpoint.json"
AUDIT_FILE = "adaptive_budget_v2.json"

DEFAULT_PRIMARY_TOKEN_LIMIT = 1_500_000
DEFAULT_EXTRA_TOKEN_LIMIT = 500_000
DEFAULT_MAX_STEPS = 120
DEFAULT_RECENT_ACTIONS = 10
# Trigger checkpoint when primary usage reaches this fraction of the primary cap.
CHECKPOINT_USAGE_FRACTION = 0.90

_WRITE_TOOL_NAMES = frozenset(
    {
        "str_replace_editor",
        "file_editor",
        "edit_file",
        "write_file",
        "str_replace",
        "create_file",
    }
)
_WRITE_COMMAND_RE = re.compile(
    r"(?:^|[\s;&|])(?:"
    r"tee\b|cat\s*>|printf\s+.*>|"
    r"python3?\s+-c\s+.*open\(|"
    r"sed\s+-i|perl\s+-i|"
    r"cp\b|mv\b|install\b|"
    r"mkdir\b|"
    r">\s*[^\s]*submission/"
    r")",
    re.IGNORECASE,
)
_SUBMISSION_PATH_RE = re.compile(r"(?:^|[\s\"'`=/])submission(?:/|$)")


@dataclass(frozen=True)
class ProgressSignals:
    has_nonempty_submission: bool
    recent_action_count: int
    recent_submission_writes: int
    recent_submission_mtimes: int
    decision: str  # "continue" | "stop"
    reason: str


def primary_token_limit(env: dict[str, str] | None = None) -> int:
    values = env or {}
    raw = str(values.get("FEATURELIFTBENCH_V2_PRIMARY_TOKEN_LIMIT", "")).strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_PRIMARY_TOKEN_LIMIT


def extra_token_limit(env: dict[str, str] | None = None) -> int:
    values = env or {}
    raw = str(values.get("FEATURELIFTBENCH_V2_EXTRA_TOKEN_LIMIT", "")).strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_EXTRA_TOKEN_LIMIT


def recent_action_window(env: dict[str, str] | None = None) -> int:
    values = env or {}
    raw = str(values.get("FEATURELIFTBENCH_V2_RECENT_ACTIONS", "")).strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return DEFAULT_RECENT_ACTIONS


def submission_is_nonempty(submission_dir: Path) -> bool:
    package = submission_dir / "featurelifted"
    if not package.is_dir():
        return False
    for path in package.rglob("*"):
        if path.is_file() and path.stat().st_size > 0:
            return True
    return False


def _parse_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _load_action_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    try:
        for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            kind = str(payload.get("kind") or "")
            if kind != "ActionEvent" and payload.get("source") != "agent":
                # Prefer ActionEvent; also accept agent-sourced actions with tool_name.
                if not (payload.get("tool_name") and payload.get("action")):
                    continue
            if kind and kind != "ActionEvent":
                continue
            events.append(payload)
    except OSError:
        return []
    return events


_EDITOR_WRITE_COMMANDS = frozenset(
    {"create", "str_replace", "insert", "write", "edit", "undo_edit"}
)


def _action_touches_submission(event: dict[str, Any]) -> bool:
    tool_name = str(event.get("tool_name") or "").strip().lower()
    action = event.get("action") if isinstance(event.get("action"), dict) else {}
    command = str(action.get("command") or "")
    path = str(
        action.get("path")
        or action.get("file_path")
        or action.get("file")
        or ""
    )
    summary = str(event.get("summary") or "")
    blob = " ".join([tool_name, command, path, summary])
    if not _SUBMISSION_PATH_RE.search(blob) and "submission/" not in blob.replace(
        "\\", "/"
    ):
        return False
    if tool_name in {"terminal", "run", "bash", "execute_bash"}:
        return bool(_WRITE_COMMAND_RE.search(command))
    if tool_name in _WRITE_TOOL_NAMES:
        # file_editor uses command=create|str_replace|view|...
        cmd = command.strip().lower()
        if not cmd or cmd in _EDITOR_WRITE_COMMANDS:
            return True
        return False
    if path and "submission" in path.replace("\\", "/"):
        return tool_name.endswith("edit") or "write" in tool_name or "replace" in tool_name
    return False


def _recent_submission_mtimes(
    submission_dir: Path,
    *,
    window_start: float | None,
    window_end: float | None,
) -> int:
    if window_start is None or window_end is None:
        return 0
    package = submission_dir / "featurelifted"
    if not package.is_dir():
        return 0
    count = 0
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if window_start <= mtime <= window_end + 1.0:
            count += 1
    return count


def evaluate_progress(
    *,
    agent_output_dir: Path,
    submission_dir: Path,
    recent_n: int = DEFAULT_RECENT_ACTIONS,
) -> ProgressSignals:
    """Decide CONTINUE vs STOP using only legal runtime signals."""

    has_submission = submission_is_nonempty(submission_dir)
    if not has_submission:
        return ProgressSignals(
            has_nonempty_submission=False,
            recent_action_count=0,
            recent_submission_writes=0,
            recent_submission_mtimes=0,
            decision="stop",
            reason="empty_or_missing_submission",
        )

    events_path = agent_output_dir / "openhands_events.jsonl"
    actions = _load_action_events(events_path)
    recent = actions[-recent_n:] if recent_n > 0 else actions
    write_count = sum(1 for event in recent if _action_touches_submission(event))
    timestamps = [
        ts
        for event in recent
        if (ts := _parse_timestamp(event.get("timestamp"))) is not None
    ]
    window_start = min(timestamps) if timestamps else None
    window_end = max(timestamps) if timestamps else None
    mtime_count = _recent_submission_mtimes(
        submission_dir,
        window_start=window_start,
        window_end=window_end,
    )
    if write_count > 0 or mtime_count > 0:
        return ProgressSignals(
            has_nonempty_submission=True,
            recent_action_count=len(recent),
            recent_submission_writes=write_count,
            recent_submission_mtimes=mtime_count,
            decision="continue",
            reason="recent_submission_progress",
        )
    return ProgressSignals(
        has_nonempty_submission=True,
        recent_action_count=len(recent),
        recent_submission_writes=0,
        recent_submission_mtimes=0,
        decision="stop",
        reason="no_recent_submission_writes",
    )


def primary_needs_checkpoint(usage: dict[str, Any], *, primary_limit: int) -> bool:
    """True when primary hit/near the 1.5M cap and may deserve a second phase."""

    if not isinstance(usage, dict):
        return False
    if usage.get("token_budget_exhausted") is True:
        return True
    total = usage.get("total_tokens")
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        return float(total) >= float(primary_limit) * CHECKPOINT_USAGE_FRACTION
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if (
        isinstance(prompt, (int, float))
        and isinstance(completion, (int, float))
        and not isinstance(prompt, bool)
        and not isinstance(completion, bool)
    ):
        return float(prompt) + float(completion) >= float(primary_limit) * CHECKPOINT_USAGE_FRACTION
    return False


def targeted_repair_openhands_appendix() -> str:
    return (
        "You are in a **Targeted Repair** budget extension. Do not restart broad "
        "repository exploration.\n\n"
        "Constraints for this phase:\n"
        "- Do not wander through `repo/` looking for new entry points.\n"
        "- Only fix unresolved issues in `submission/featurelifted/` "
        "(API gaps, imports, dependencies, agent-authored tests you already wrote).\n"
        "- After each meaningful change, immediately verify with a local check "
        "(for example `python -c \"from featurelifted import ...\"` or tests you authored).\n"
        "- Never hunt for benchmark evaluator tests; they are not mounted.\n"
        "- Prefer small, focused edits over rewriting the package.\n"
    )


def targeted_repair_task_appendix() -> str:
    return (
        "## Targeted Repair Mode\n\n"
        + targeted_repair_openhands_appendix()
        + "\n"
    )


def write_checkpoint(
    agent_output_dir: Path,
    *,
    signals: ProgressSignals,
    primary_usage: dict[str, Any],
    primary_limit: int,
    extra_limit: int,
    granted_extra: bool,
) -> dict[str, Any]:
    payload = {
        "schema_version": "featureliftbench.adaptive_budget_v2_checkpoint.v1",
        "decision": signals.decision,
        "reason": signals.reason,
        "granted_extra": granted_extra,
        "primary_token_limit": primary_limit,
        "extra_token_limit": extra_limit,
        "signals": {
            "has_nonempty_submission": signals.has_nonempty_submission,
            "recent_action_count": signals.recent_action_count,
            "recent_submission_writes": signals.recent_submission_writes,
            "recent_submission_mtimes": signals.recent_submission_mtimes,
        },
        "primary_usage": {
            key: primary_usage.get(key)
            for key in (
                "total_tokens",
                "prompt_tokens",
                "completion_tokens",
                "assistant_steps",
                "token_budget_exhausted",
                "available",
            )
            if key in primary_usage or key == "token_budget_exhausted"
        },
    }
    agent_output_dir.mkdir(parents=True, exist_ok=True)
    path = agent_output_dir / CHECKPOINT_FILE
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def aggregate_phase_usage(
    named_agents: list[tuple[str, dict[str, Any] | None]],
) -> dict[str, Any]:
    metric_names = (
        "api_calls",
        "assistant_steps",
        "total_messages",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "effective_uncached_prompt_tokens",
        "tool_alias_normalizations",
        "trace_tokens",
        "billed_tokens",
    )
    totals: dict[str, Any] = {name: 0 for name in metric_names}
    phases: list[dict[str, Any]] = []
    for phase_name, agent in named_agents:
        if not isinstance(agent, dict) or not agent:
            continue
        usage = agent.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        phase: dict[str, Any] = {
            "phase": phase_name,
            "duration_seconds": agent.get("duration_seconds", 0.0),
            "passed": agent.get("passed", False),
        }
        for name in metric_names:
            value = usage.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[name] += int(value)
                phase[name] = int(value)
        if usage.get("token_budget_exhausted") is True:
            phase["token_budget_exhausted"] = True
        phases.append(phase)
    totals["available"] = bool(phases)
    totals["duration_seconds"] = sum(
        float(phase.get("duration_seconds") or 0.0) for phase in phases
    )
    totals["phases"] = phases
    totals["token_budget_exhausted"] = any(
        phase.get("token_budget_exhausted") is True for phase in phases
    )
    return totals


def write_audit(
    output_dir: Path,
    *,
    checkpoint: dict[str, Any],
    agent_primary: dict[str, Any] | None,
    agent_repair: dict[str, Any] | None,
    repair_rounds_used: int,
) -> dict[str, Any]:
    usage_totals = aggregate_phase_usage(
        [
            ("primary", agent_primary),
            ("repair", agent_repair),
        ]
    )
    payload = {
        "schema_version": "featureliftbench.adaptive_budget_v2_audit.v1",
        "arm": "adaptive_budget_v2",
        "checkpoint": checkpoint,
        "repair_rounds_used": repair_rounds_used,
        "agent_primary": agent_primary,
        "agent_repair": agent_repair,
        "usage_totals": usage_totals,
    }
    path = output_dir / AUDIT_FILE
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
