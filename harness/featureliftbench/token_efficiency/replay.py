"""Isolated reconstruction of submission states at tool-completion boundaries."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .artifacts import (
    archive_entries,
    empty_artifact_hash,
    hash_tree,
    iter_artifact_entries,
    write_entries,
)
from .constants import EDITOR_WRITE_COMMANDS, PINNED_REPLAY_IMAGE
from .events import ToolCompletion, load_events, load_persistence_events, pair_completions
from .ledger import RunLedger, tokens_for_completion
from .scope import OfficialRun, repo_root
from .source_support import materialize_frozen_repo
from .util import write_json


class TerminalRunner(Protocol):
    def run(self, command: str, timeout: int = 120) -> "CommandResult":
        ...

    def close(self) -> None:
        ...


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    isolated: bool = True


@dataclass
class TimelineState:
    state_index: int
    event_id: str
    tool_call_id: str
    event_time: float | None
    artifact_hash: str
    causal_order_status: str
    mutation_kind: str
    reconstruction_status: str
    token_alignment_status: str
    accounting_basis: str
    cumulative_tokens: int | None
    cumulative_tokens_lower: int | None
    cumulative_tokens_upper: int | None
    eval_key: str = ""
    llm_response_id: str = ""
    notes: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayOutcome:
    timeline: list[TimelineState]
    unique_hashes: list[str]
    last_hash: str
    disk_hash: str | None
    last_matches_disk: bool
    reconstruction_status: str
    full_timeline_covered: bool
    editor_writes: int
    terminal_runs: int
    terminal_errors: int
    unmatched_tools: int
    error: str | None = None
    workspace: Path | None = None


class DockerTerminal:
    """Long-lived, no-network replay container. Commands are historical data."""

    def __init__(
        self,
        workspace: Path,
        *,
        tmp: Path | None = None,
        image: str = PINNED_REPLAY_IMAGE,
        memory: str = "4g",
        cpus: str = "2",
        pids: str = "256",
    ) -> None:
        self.workspace = workspace.resolve()
        self.tmp = tmp.resolve() if tmp is not None else None
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.pids = pids
        self.container = f"flb-te-replay-{uuid.uuid4().hex[:12]}"
        self._started = False

    def start(self) -> None:
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            self.container,
            "--network",
            "none",
            "--memory",
            self.memory,
            "--cpus",
            self.cpus,
            "--pids-limit",
            self.pids,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--entrypoint",
            "sleep",
            "-w",
            "/flb/workspace",
            "-v",
            f"{self.workspace}:/flb/workspace:rw",
        ]
        if self.tmp is not None:
            self.tmp.mkdir(parents=True, exist_ok=True)
            command.extend(["-v", f"{self.tmp}:/tmp:rw"])
        else:
            command.extend(["--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=2g"])
        command.extend([self.image, "infinity"])
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"replay container failed: {completed.stderr.strip() or completed.stdout.strip()}"
            )
        self._started = True

    def run(self, command: str, timeout: int = 120) -> CommandResult:
        if "\x00" in command:
            return CommandResult(
                returncode=1,
                stdout="",
                stderr="embedded_null_in_command",
                isolated=True,
            )
        if not self._started:
            self.start()
        exec_cmd = [
            "docker",
            "exec",
            "-u",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            "HOME=/tmp",
            "-e",
            "TMPDIR=/tmp",
            "-e",
            "PYTHONUNBUFFERED=1",
            "-w",
            "/flb/workspace",
            self.container,
            "bash",
            "-lc",
            command,
        ]
        try:
            completed = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=max(1, timeout),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                returncode=124,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=f"replay exec timed out after {timeout}s",
                timed_out=True,
            )
        return CommandResult(
            returncode=int(completed.returncode or 0),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    def close(self) -> None:
        if not self._started:
            return
        subprocess.run(
            ["docker", "rm", "-f", self.container],
            capture_output=True,
            check=False,
        )
        self._started = False


class ScriptedTerminal:
    """Test double: apply caller-provided side effects, never host bash."""

    def __init__(self, handler: Callable[[str], CommandResult | None] | None = None) -> None:
        self.handler = handler
        self.commands: list[str] = []

    def run(self, command: str, timeout: int = 120) -> CommandResult:
        del timeout
        self.commands.append(command)
        if self.handler is not None:
            result = self.handler(command)
            if result is not None:
                return result
        return CommandResult(returncode=0, stdout="", stderr="")

    def close(self) -> None:
        return None


class ReplayWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.workspace = root / "workspace"
        self.tmp = root / "tmp"
        self.submission = self.workspace / "submission"

    def prepare_from_paths(
        self,
        *,
        repo_src: Path,
        task_md: Path,
        metadata: Path,
        requirements_lock: Path | None,
    ) -> None:
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        if self.tmp.exists():
            shutil.rmtree(self.tmp)
        self.workspace.mkdir(parents=True)
        self.tmp.mkdir(parents=True)
        shutil.copytree(repo_src, self.workspace / "repo", symlinks=True)
        shutil.copy2(task_md, self.workspace / "TASK.md")
        shutil.copy2(metadata, self.workspace / "metadata.json")
        if requirements_lock and requirements_lock.is_file():
            shutil.copy2(requirements_lock, self.workspace / "requirements.lock")
        (self.submission / "featurelifted").mkdir(parents=True, exist_ok=True)

    def resolve_container_path(self, path: str) -> Path | None:
        if not path or "\x00" in path:
            return None
        text = path.replace("\\", "/")
        if text.startswith("/flb/workspace/"):
            rel = text[len("/flb/workspace/") :]
            dest = (self.workspace / rel).resolve()
            parent = self.workspace.resolve()
        elif text.startswith("/tmp/"):
            rel = text[len("/tmp/") :]
            dest = (self.tmp / rel).resolve()
            parent = self.tmp.resolve()
        elif text == "/tmp":
            return self.tmp.resolve()
        elif "/submission/" in text:
            dest = (self.workspace / "submission" / text.split("/submission/", 1)[1]).resolve()
            parent = self.workspace.resolve()
        else:
            return None
        try:
            dest.relative_to(parent)
        except ValueError:
            return None
        return dest

    def apply_editor(self, path: str, content: str) -> bool:
        dest = self.resolve_container_path(path)
        if dest is None:
            return False
        try:
            if dest.exists() and dest.is_dir():
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content.encode("utf-8"))
            return True
        except (OSError, ValueError):
            return False

    def delete(self, path: str) -> bool:
        dest = self.resolve_container_path(path)
        if dest is None or not dest.exists():
            return False
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
        return True

    def snapshot_submission(self) -> tuple[str, list]:
        if not self.submission.exists():
            return empty_artifact_hash(), []
        try:
            entries = iter_artifact_entries(self.submission)
            return hash_tree(self.submission), entries
        except (OSError, ValueError):
            return empty_artifact_hash(), []


def replay_run(
    run: OfficialRun,
    *,
    ledger: RunLedger,
    cas_dir: Path,
    work_root: Path,
    root: Path | None = None,
    terminal: TerminalRunner | None = None,
    use_docker: bool = True,
    keep_workspace: bool = False,
) -> ReplayOutcome:
    base = (root or repo_root()).resolve()
    mapped = Path(run.mapped_run_dir)
    events_path = mapped / "agent" / "openhands_events.jsonl"
    if events_path.is_file() and events_path.stat().st_size > 0:
        events = load_events(events_path)
    else:
        events = load_persistence_events(mapped / "agent" / "openhands_persistence")
    completions, pair_stats = pair_completions(events)
    work = Path(tempfile.mkdtemp(prefix="flb-te-ws-", dir=str(work_root))) if keep_workspace else Path(
        tempfile.mkdtemp(prefix="flb-te-ws-")
    )
    sandbox = ReplayWorkspace(work)
    task_dir = base / "benchmark" / "tasks" / run.task_id
    repo_cache = work_root / "source_cache"
    try:
        repo_src = materialize_frozen_repo(base, run.task_id, repo_cache)
        sandbox.prepare_from_paths(
            repo_src=repo_src,
            task_md=task_dir / "TASK.md",
            metadata=task_dir / "metadata.json",
            requirements_lock=task_dir / "requirements.lock",
        )
    except Exception as exc:  # noqa: BLE001
        return ReplayOutcome(
            timeline=[],
            unique_hashes=[],
            last_hash=empty_artifact_hash(),
            disk_hash=_disk_hash(mapped),
            last_matches_disk=False,
            reconstruction_status="unresolved",
            full_timeline_covered=False,
            editor_writes=0,
            terminal_runs=0,
            terminal_errors=0,
            unmatched_tools=int(pair_stats.get("unmatched_observations") or 0),
            error=f"initial_state:{type(exc).__name__}:{exc}",
        )

    owned_terminal = False
    if terminal is None and use_docker:
        terminal = DockerTerminal(sandbox.workspace, tmp=sandbox.tmp)
        owned_terminal = True
        try:
            terminal.start()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            if owned_terminal:
                terminal.close()
            return ReplayOutcome(
                timeline=[],
                unique_hashes=[],
                last_hash=empty_artifact_hash(),
                disk_hash=_disk_hash(mapped),
                last_matches_disk=False,
                reconstruction_status="unresolved",
                full_timeline_covered=False,
                editor_writes=0,
                terminal_runs=0,
                terminal_errors=0,
                unmatched_tools=int(pair_stats.get("unmatched_observations") or 0),
                error=f"replay_container:{type(exc).__name__}:{exc}",
            )

    timeline: list[TimelineState] = []
    unique: list[str] = []
    seen_hashes: set[str] = set()
    seen_responses: set[str] = set()
    editor_writes = 0
    terminal_runs = 0
    terminal_errors = 0
    unknown_before_pass = False
    reconstruction_notes: list[str] = []

    initial_hash, initial_entries = sandbox.snapshot_submission()
    _store_cas(cas_dir, run.task_id, initial_hash, initial_entries)
    unique.append(initial_hash)
    seen_hashes.add(initial_hash)
    timeline.append(
        TimelineState(
            state_index=0,
            event_id="initial",
            tool_call_id="",
            event_time=None,
            artifact_hash=initial_hash,
            causal_order_status="exact",
            mutation_kind="initial",
            reconstruction_status="ok",
            token_alignment_status="exact" if ledger.token_usage_status == "complete" else ledger.token_usage_status,
            accounting_basis=ledger.accounting_basis,
            cumulative_tokens=0 if ledger.token_usage_status == "complete" else None,
            cumulative_tokens_lower=0 if ledger.token_usage_status == "complete" else None,
            cumulative_tokens_upper=0 if ledger.token_usage_status == "complete" else None,
        )
    )

    try:
        for completion in completions:
            mutated, status, kind = _apply_completion(sandbox, terminal, completion)
            if completion.unmatched:
                unknown_before_pass = True
                reconstruction_notes.append(f"unmatched:{completion.event_id}")
            if completion.mutation_kind in {"editor_unknown", "terminal_error"} and _could_mutate(completion):
                unknown_before_pass = True
            if completion.tool_name == "file_editor" and kind == "editor_write":
                editor_writes += 1
            if completion.tool_name == "terminal" and kind not in {"none"}:
                terminal_runs += 1
                if status != "ok":
                    terminal_errors += 1
            if not mutated and kind in {"none", "editor_failed"}:
                continue
            digest, entries = sandbox.snapshot_submission()
            exact, lower, upper, token_status = tokens_for_completion(
                ledger, completion, seen_responses
            )
            if completion.llm_response_id:
                seen_responses.add(completion.llm_response_id)
            if digest not in seen_hashes:
                seen_hashes.add(digest)
                unique.append(digest)
                _store_cas(cas_dir, run.task_id, digest, entries)
            timeline.append(
                TimelineState(
                    state_index=len(timeline),
                    event_id=completion.event_id,
                    tool_call_id=completion.tool_call_id,
                    event_time=completion.timestamp,
                    artifact_hash=digest,
                    causal_order_status="unresolved" if completion.unmatched else "exact",
                    mutation_kind=kind,
                    reconstruction_status=status,
                    token_alignment_status=token_status,
                    accounting_basis=ledger.accounting_basis,
                    cumulative_tokens=exact,
                    cumulative_tokens_lower=lower,
                    cumulative_tokens_upper=upper,
                    llm_response_id=completion.llm_response_id,
                )
            )
    finally:
        if owned_terminal and terminal is not None:
            terminal.close()

    disk_hash = _disk_hash(mapped)
    last_hash = timeline[-1].artifact_hash if timeline else empty_artifact_hash()
    last_matches = bool(disk_hash and last_hash == disk_hash)
    full = (
        not unknown_before_pass
        and pair_stats.get("unmatched_observations", 0) == 0
        and last_matches
        and all(item.reconstruction_status == "ok" for item in timeline)
    )
    reconstruction = "ok" if full else ("partial" if timeline else "unresolved")
    if not keep_workspace:
        shutil.rmtree(work, ignore_errors=True)
        workspace_path = None
    else:
        workspace_path = sandbox.workspace
    return ReplayOutcome(
        timeline=timeline,
        unique_hashes=unique,
        last_hash=last_hash,
        disk_hash=disk_hash,
        last_matches_disk=last_matches,
        reconstruction_status=reconstruction,
        full_timeline_covered=full,
        editor_writes=editor_writes,
        terminal_runs=terminal_runs,
        terminal_errors=terminal_errors,
        unmatched_tools=int(pair_stats.get("unmatched_observations") or 0),
        error="; ".join(reconstruction_notes) or None,
        workspace=workspace_path,
    )


def replay_from_events(
    *,
    events_path: Path,
    repo_src: Path,
    task_md: Path,
    metadata: Path,
    ledger: RunLedger,
    terminal: TerminalRunner,
    requirements_lock: Path | None = None,
) -> ReplayOutcome:
    """Lightweight replay used by tests; does not touch official run directories."""

    events = load_events(events_path)
    completions, pair_stats = pair_completions(events)
    work = Path(tempfile.mkdtemp(prefix="flb-te-test-"))
    sandbox = ReplayWorkspace(work)
    sandbox.prepare_from_paths(
        repo_src=repo_src,
        task_md=task_md,
        metadata=metadata,
        requirements_lock=requirements_lock,
    )
    timeline: list[TimelineState] = []
    unique: list[str] = []
    seen: set[str] = set()
    seen_responses: set[str] = set()
    initial_hash, _entries = sandbox.snapshot_submission()
    unique.append(initial_hash)
    seen.add(initial_hash)
    timeline.append(
        TimelineState(
            state_index=0,
            event_id="initial",
            tool_call_id="",
            event_time=None,
            artifact_hash=initial_hash,
            causal_order_status="exact",
            mutation_kind="initial",
            reconstruction_status="ok",
            token_alignment_status="exact",
            accounting_basis=ledger.accounting_basis,
            cumulative_tokens=0,
            cumulative_tokens_lower=0,
            cumulative_tokens_upper=0,
        )
    )
    editor_writes = 0
    terminal_runs = 0
    try:
        for completion in completions:
            mutated, status, kind = _apply_completion(sandbox, terminal, completion)
            if completion.tool_name == "file_editor" and kind == "editor_write":
                editor_writes += 1
            if completion.tool_name == "terminal" and kind != "none":
                terminal_runs += 1
            if not mutated and kind in {"none", "editor_failed"}:
                continue
            digest, _ = sandbox.snapshot_submission()
            exact, lower, upper, token_status = tokens_for_completion(
                ledger, completion, seen_responses
            )
            if completion.llm_response_id:
                seen_responses.add(completion.llm_response_id)
            if digest not in seen:
                seen.add(digest)
                unique.append(digest)
            timeline.append(
                TimelineState(
                    state_index=len(timeline),
                    event_id=completion.event_id,
                    tool_call_id=completion.tool_call_id,
                    event_time=completion.timestamp,
                    artifact_hash=digest,
                    causal_order_status="unresolved" if completion.unmatched else "exact",
                    mutation_kind=kind,
                    reconstruction_status=status,
                    token_alignment_status=token_status,
                    accounting_basis=ledger.accounting_basis,
                    cumulative_tokens=exact,
                    cumulative_tokens_lower=lower,
                    cumulative_tokens_upper=upper,
                    llm_response_id=completion.llm_response_id,
                )
            )
    finally:
        terminal.close()
        shutil.rmtree(work, ignore_errors=True)
    last_hash = timeline[-1].artifact_hash
    return ReplayOutcome(
        timeline=timeline,
        unique_hashes=unique,
        last_hash=last_hash,
        disk_hash=None,
        last_matches_disk=False,
        reconstruction_status="ok",
        full_timeline_covered=pair_stats.get("unmatched_observations", 0) == 0,
        editor_writes=editor_writes,
        terminal_runs=terminal_runs,
        terminal_errors=0,
        unmatched_tools=int(pair_stats.get("unmatched_observations") or 0),
    )


def _apply_completion(
    sandbox: ReplayWorkspace,
    terminal: TerminalRunner | None,
    completion: ToolCompletion,
) -> tuple[bool, str, str]:
    kind = completion.mutation_kind
    if "\x00" in (completion.path or "") or "\x00" in (completion.command or ""):
        return False, "unresolved", kind
    try:
        return _apply_completion_inner(sandbox, terminal, completion)
    except (OSError, ValueError):
        return False, "unresolved", kind


def _apply_completion_inner(
    sandbox: ReplayWorkspace,
    terminal: TerminalRunner | None,
    completion: ToolCompletion,
) -> tuple[bool, str, str]:
    kind = completion.mutation_kind
    if completion.tool_name == "file_editor":
        if kind == "none" or completion.editor_command == "view":
            return False, "ok", "none"
        if kind == "editor_failed":
            return False, "ok", "editor_failed"
        if kind == "editor_write" and completion.new_content is not None:
            ok = sandbox.apply_editor(completion.path, completion.new_content)
            return ok, "ok" if ok else "unresolved", "editor_write"
        if kind == "delete":
            ok = sandbox.delete(completion.path)
            return True, "ok" if ok else "unresolved", "delete"
        return False, "unresolved", kind
    if completion.tool_name == "terminal":
        if kind == "none":
            return False, "ok", "none"
        if terminal is None:
            return False, "unresolved", kind
        result = terminal.run(completion.command, timeout=120)
        status = "ok"
        if result.timed_out:
            status = "unresolved"
        mutated = True
        return mutated, status, kind
    return False, "ok", "none"


def _could_mutate(completion: ToolCompletion) -> bool:
    return completion.mutation_kind not in {"none", "editor_failed"}


def _store_cas(cas_dir: Path, task_id: str, digest: str, entries: list) -> None:
    archive = cas_dir / task_id / f"{digest}.tar.gz"
    if archive.is_file():
        return
    archive_entries(archive, entries)


def _disk_hash(mapped: Path) -> str | None:
    submission = mapped / "submission"
    if not submission.is_dir():
        return None
    try:
        return hash_tree(submission)
    except (OSError, ValueError):
        return None


def write_timeline(path: Path, timeline: list[TimelineState]) -> None:
    from .util import write_jsonl

    write_jsonl(path, [item.to_json() for item in timeline])
