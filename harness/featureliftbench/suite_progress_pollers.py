"""Agent-specific suite progress pollers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from typing import Protocol

from .openhands_usage import DEFAULT_STDOUT_LOG_FILENAME
from .openhands_usage import parse_openhands_progress_snapshot
from .openhands_usage import resolve_events_path
from .suite_progress_mini import format_mini_task_status
from .suite_progress_mini import parse_mini_progress_from_log
from .suite_progress_mini import parse_mini_token_total_from_trajectory

MetricKind = Literal["tokens", "events", "steps"]


@dataclass(frozen=True)
class TaskProgressSnapshot:
    status: str
    metric_value: int | None
    metric_kind: MetricKind


class ProgressPoller(Protocol):
    main_metric_kind: MetricKind

    def poll(self, agent_dir: Path) -> TaskProgressSnapshot | None: ...


@dataclass(frozen=True)
class MiniProgressPoller:
    main_metric_kind: MetricKind = "tokens"

    def poll(self, agent_dir: Path) -> TaskProgressSnapshot | None:
        step_status = parse_mini_progress_from_log(agent_dir / "stdout.log")
        if step_status is None:
            step_status = _parse_mini_step_from_trajectory(agent_dir / "trajectory.json")
        if step_status is None:
            return None
        tokens = parse_mini_token_total_from_trajectory(agent_dir / "trajectory.json")
        status, tokens = format_mini_task_status(step_status=step_status, tokens=tokens)
        return TaskProgressSnapshot(
            status=status,
            metric_value=tokens,
            metric_kind="tokens" if tokens is not None else "steps",
        )


def _parse_mini_step_from_trajectory(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    steps = sum(
        1
        for message in data.get("messages") or []
        if isinstance(message, dict) and message.get("role") == "assistant"
    )
    return f"Step {steps}" if steps > 0 else None


@dataclass(frozen=True)
class OpenHandsProgressPoller:
    main_metric_kind: MetricKind = "events"

    def poll(self, agent_dir: Path) -> TaskProgressSnapshot | None:
        log_path = resolve_events_path(
            agent_dir,
            stdout_log=agent_dir / DEFAULT_STDOUT_LOG_FILENAME,
        )
        if log_path is None:
            return None
        snapshot = parse_openhands_progress_snapshot(log_path)
        if snapshot is None:
            return None
        if snapshot.total_tokens is not None and snapshot.total_tokens > 0:
            return TaskProgressSnapshot(
                status=snapshot.status,
                metric_value=snapshot.total_tokens,
                metric_kind="tokens",
            )
        return TaskProgressSnapshot(
            status=snapshot.status,
            metric_value=snapshot.event_count,
            metric_kind="events",
        )


@dataclass(frozen=True)
class FeatureLiftProgressPoller:
    main_metric_kind: MetricKind = "steps"

    def poll(self, agent_dir: Path) -> TaskProgressSnapshot | None:
        audit_path = agent_dir / "context_audit.jsonl"
        if not audit_path.is_file():
            return None
        try:
            lines = audit_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None

        step_count = 0
        prompt_tokens = 0
        saw_tokens = False
        last_phase = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            step_count += 1
            phase = record.get("phase")
            if isinstance(phase, str) and phase:
                last_phase = phase
            prompt = record.get("prompt_tokens")
            if isinstance(prompt, int) and prompt >= 0:
                prompt_tokens += prompt
                saw_tokens = True

        if step_count <= 0:
            return None
        phase_label = last_phase or "running"
        status = f"Step {step_count} · {phase_label}"
        if saw_tokens and prompt_tokens > 0:
            return TaskProgressSnapshot(
                status=status,
                metric_value=prompt_tokens,
                metric_kind="tokens",
            )
        return TaskProgressSnapshot(
            status=status,
            metric_value=step_count,
            metric_kind="steps",
        )


def normalize_agent_name(agent: str) -> str:
    return agent.strip().lower().replace("_", "-")


def resolve_progress_poller(agent: str) -> ProgressPoller:
    normalized = normalize_agent_name(agent)
    if normalized in {"openhands", "openhands-agent", "openhandsagent"}:
        return OpenHandsProgressPoller()
    if normalized in {"featurelift-agent", "featureliftagent", "featurelift"}:
        return FeatureLiftProgressPoller()
    return MiniProgressPoller()
