"""Rich progress UI for FeatureLiftBench suite runs."""

from __future__ import annotations

import collections
import contextlib
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Iterator
from typing import Literal

from rich.console import Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .suite_progress_mini import format_mini_task_status
from .suite_progress_mini import parse_mini_progress_from_log
from .suite_progress_mini import parse_mini_token_total_from_trajectory
from .suite_progress_mini import format_token_count
from .suite_progress_pollers import MetricKind
from .suite_progress_pollers import resolve_progress_poller

MetricKind = MetricKind


def _shorten_str(value: str, max_len: int, *, shorten_left: bool = False) -> str:
    if not shorten_left:
        text = value[: max_len - 3] + "..." if len(value) > max_len else value
    else:
        text = "..." + value[-max_len + 3 :] if len(value) > max_len else value
    return f"{text:<{max_len}}"


def resolve_agent_log_dir(
    output_dir: Path,
    task_id: str,
    *,
    layout: Literal["suite", "flat"] = "suite",
) -> Path:
    if layout == "flat":
        return output_dir / "agent"
    return output_dir / task_id / "agent"


def parse_mini_step_from_trajectory(path: Path) -> str | None:
    """Extract a coarse mini-swe-agent step count from trajectory messages."""

    if not path.is_file():
        return None
    try:
        import json

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


def poll_agent_task_status(agent_dir: Path) -> tuple[str, int | None] | None:
    """Return the latest mini-swe-agent status and token total for legacy callers."""

    step_status = parse_mini_progress_from_log(agent_dir / "stdout.log")
    if step_status is None:
        step_status = parse_mini_step_from_trajectory(agent_dir / "trajectory.json")
    if step_status is None:
        return None
    tokens = parse_mini_token_total_from_trajectory(agent_dir / "trajectory.json")
    return format_mini_task_status(step_status=step_status, tokens=tokens)


class SuiteBatchProgressManager:
    """Manage overall and per-task progress for a FeatureLiftBench suite run."""

    def __init__(
        self,
        num_tasks: int,
        *,
        agent: str = "mini-swe-agent",
        layout: Literal["suite", "flat"] = "suite",
    ) -> None:
        self._layout = layout
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._total_tasks = num_tasks
        self._poller = resolve_progress_poller(agent)
        self._default_metric_kind: MetricKind = self._poller.main_metric_kind
        self._spinner_tasks: dict[str, TaskID] = {}
        self._active_tasks: set[str] = set()
        self._task_metrics: dict[str, tuple[int, MetricKind]] = {}
        self._instances_by_exit_status: dict[str | None, list[str]] = collections.defaultdict(list)

        self._main_progress_bar = Progress(
            SpinnerColumn(spinner_name="dots2"),
            TextColumn("[progress.description]{task.description} ({task.fields[main_metric]})"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TextColumn("[cyan]{task.fields[eta]}[/cyan]"),
            speed_estimate_period=60 * 5,
        )
        self._task_progress_bar = Progress(
            SpinnerColumn(spinner_name="dots2"),
            TextColumn("{task.fields[label]}"),
            TextColumn("{task.fields[status]}"),
            TimeElapsedColumn(),
        )
        self._main_task_id = self._main_progress_bar.add_task(
            "[cyan]Overall Progress",
            total=num_tasks,
            main_metric=self._empty_main_metric_text(),
            eta="",
        )
        self.render_group = Group(self._main_progress_bar, Table(), self._task_progress_bar)

    @property
    def n_completed(self) -> int:
        return sum(len(items) for items in self._instances_by_exit_status.values())

    def active_task_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._active_tasks)

    def _empty_main_metric_text(self) -> str:
        if self._default_metric_kind == "events":
            return "0 events"
        if self._default_metric_kind == "steps":
            return "0 steps"
        return "0 toks"

    def _get_eta_text(self) -> str:
        completed = self.n_completed
        if completed <= 0:
            return ""
        try:
            elapsed = time.time() - self._start_time
            remaining = elapsed / completed * (self._total_tasks - completed)
            return f"eta: {timedelta(seconds=int(remaining))}"
        except ZeroDivisionError:
            return ""

    def _format_metric(self, value: int, metric_kind: MetricKind) -> str:
        if metric_kind == "events":
            return f"{value:,} events"
        if metric_kind == "steps":
            return f"{value:,} steps"
        return f"{format_token_count(value)} toks"

    def _main_metric_text(self) -> str:
        with self._lock:
            if not self._task_metrics:
                return self._empty_main_metric_text()
            total = sum(value for value, _kind in self._task_metrics.values())
            if total <= 0:
                return self._empty_main_metric_text()
            kinds = {kind for _value, kind in self._task_metrics.values()}
            metric_kind = (
                "tokens"
                if "tokens" in kinds
                else ("events" if "events" in kinds else self._default_metric_kind)
            )
            return self._format_metric(total, metric_kind)

    def _update_main_bar(self) -> None:
        self._main_progress_bar.update(
            self._main_task_id,
            main_metric=self._main_metric_text(),
            eta=self._get_eta_text(),
        )

    def update_exit_status_table(self) -> None:
        table = Table()
        table.add_column("Exit Status")
        table.add_column("Count", justify="right", style="bold cyan")
        table.add_column("Most recent tasks")
        with self._lock:
            sorted_items = sorted(
                self._instances_by_exit_status.items(),
                key=lambda item: len(item[1]),
                reverse=True,
            )
            for status, tasks in sorted_items:
                label = status or "unknown"
                recent = _shorten_str(", ".join(reversed(tasks)), 55)
                table.add_row(label, str(len(tasks)), recent)
        self.render_group.renderables[1] = table

    def on_task_start(self, task_id: str) -> None:
        with self._lock:
            self._active_tasks.add(task_id)
            self._spinner_tasks[task_id] = self._task_progress_bar.add_task(
                description=f"Task {task_id}",
                status="starting",
                total=None,
                label=_shorten_str(task_id, 25, shorten_left=True),
            )
        self._update_main_bar()

    def update_task_status(
        self,
        task_id: str,
        message: str,
        *,
        tokens: int | None = None,
        metric_value: int | None = None,
        metric_kind: MetricKind | None = None,
    ) -> None:
        value = metric_value if metric_value is not None else tokens
        kind = metric_kind or ("tokens" if tokens is not None else self._default_metric_kind)
        with self._lock:
            spinner_id = self._spinner_tasks.get(task_id)
            if spinner_id is None:
                return
            if value is not None and value >= 0:
                self._task_metrics[task_id] = (value, kind)
            self._task_progress_bar.update(
                spinner_id,
                status=_shorten_str(message, 30),
                label=_shorten_str(task_id, 25, shorten_left=True),
            )
        self._update_main_bar()

    def on_task_end(self, task_id: str, exit_status: str | None) -> None:
        with self._lock:
            self._active_tasks.discard(task_id)
            self._task_metrics.pop(task_id, None)
            try:
                self._task_progress_bar.remove_task(self._spinner_tasks.pop(task_id))
            except KeyError:
                pass
            self._instances_by_exit_status[exit_status].append(task_id)
            self._main_progress_bar.update(self._main_task_id, advance=1, eta=self._get_eta_text())
        self.update_exit_status_table()
        self._update_main_bar()

    def poll_task_logs(self, output_dir: Path) -> None:
        for task_id in self.active_task_ids():
            agent_dir = resolve_agent_log_dir(output_dir, task_id, layout=self._layout)
            snapshot = self._poller.poll(agent_dir)
            if snapshot is None:
                continue
            self.update_task_status(
                task_id,
                snapshot.status,
                metric_value=snapshot.metric_value,
                metric_kind=snapshot.metric_kind,
            )


@contextlib.contextmanager
def live_suite_progress(
    *,
    num_tasks: int,
    output_dir: Path,
    agent: str = "mini-swe-agent",
    refresh_per_second: float = 4.0,
    layout: Literal["suite", "flat"] = "suite",
) -> Iterator[SuiteBatchProgressManager]:
    """Render suite progress with Rich Live and poll running agent logs."""

    manager = SuiteBatchProgressManager(num_tasks, agent=agent, layout=layout)
    stop_event = threading.Event()

    def poll_loop() -> None:
        while not stop_event.wait(1.0):
            manager.poll_task_logs(output_dir)

    poll_thread = threading.Thread(target=poll_loop, name="featureliftbench-suite-progress", daemon=True)
    with Live(manager.render_group, refresh_per_second=refresh_per_second, transient=False):
        poll_thread.start()
        try:
            yield manager
        finally:
            stop_event.set()
            poll_thread.join(timeout=2.0)
