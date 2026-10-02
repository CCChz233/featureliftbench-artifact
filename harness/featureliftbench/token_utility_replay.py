"""Replay OpenHands trajectories into submission/featurelifted snapshots.

Offline gold-labeling only. Not an agent method. Successful file_editor
observations carry full ``new_content``; mutating terminal commands are
executed in a sandbox with ``/flb/workspace`` rewritten.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


EDITOR_WRITE_COMMANDS = frozenset(
    {"create", "str_replace", "insert", "write", "edit", "undo_edit"}
)
TOKEN_MARKS = (1_000_000, 1_500_000, 2_000_000)
IGNORE_NAME_PARTS = ("__pycache__", ".pyc", ".pyo", ".DS_Store")
PYTEST_RE = re.compile(r"\bpytest\b|\bpython3?\s+-m\s+pytest\b")
MUTATING_RE = re.compile(
    r"""
    \b(cp|mv|rm|mkdir|touch|install|rsync|ln|chmod|chown|install)\b
    |sed\s+-i
    |tee\s
    |cat\s*>
    |cat\s*>>
    |>>
    |<<
    |open\s*\(
    |write_text
    |write_bytes
    |Path\(
    """,
    re.VERBOSE,
)
INSPECTION_RE = re.compile(
    r"^\s*(ls|head|tail|grep|rg|find|wc|sed\s+-n|nl|file|stat|tree|du|cat)\b"
)


def parse_ts(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def load_billed_calls(audit_path: Path) -> list[tuple[float, int, int]]:
    calls: list[tuple[float, int]] = []
    if not audit_path.is_file():
        return []
    for line in audit_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = parse_ts(payload.get("timestamp"))
        if ts is None:
            continue
        prompt = payload.get("prompt_tokens") or 0
        completion = payload.get("completion_tokens") or 0
        total = payload.get("total_tokens")
        if not isinstance(total, (int, float)):
            total = prompt + completion
        calls.append((ts, int(total)))
    calls.sort(key=lambda item: item[0])
    out: list[tuple[float, int, int]] = []
    cumulative = 0
    for ts, billed in calls:
        cumulative += billed
        out.append((ts, billed, cumulative))
    return out


def tokens_at(calls: list[tuple[float, int, int]], ts: float | None) -> int | None:
    if not calls or ts is None:
        return None
    last = None
    for call_ts, _billed, cumulative in calls:
        if call_ts <= ts + 1.0:
            last = cumulative
        else:
            break
    return last if last is not None else 0


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


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


def should_ignore(relpath: str) -> bool:
    parts = relpath.replace("\\", "/").split("/")
    if any(part == "__pycache__" or part.endswith((".pyc", ".pyo")) for part in parts):
        return True
    return any(part in {".DS_Store"} for part in parts)


def package_files(pkg: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if not pkg.is_dir():
        return files
    for path in pkg.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(pkg).as_posix()
        if should_ignore(rel):
            continue
        files[rel] = path.read_bytes()
    return files


def tree_hash(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[rel])
        digest.update(b"\n")
    return digest.hexdigest()


def write_tree(pkg: Path, files: dict[str, bytes]) -> None:
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        dest = pkg / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def looks_mutating(command: str) -> bool:
    return bool(MUTATING_RE.search(command))


def pytest_only(command: str) -> bool:
    if not PYTEST_RE.search(command):
        return False
    return not looks_mutating(command)


def inspection_only(command: str) -> bool:
    compact = " ".join(command.strip().split())
    if looks_mutating(compact):
        return False
    if PYTEST_RE.search(compact):
        return True
    return bool(INSPECTION_RE.search(compact))


def should_run_terminal(command: str) -> bool:
    if not command.strip() or pytest_only(command):
        return False
    if inspection_only(command):
        return False
    blob = command.replace("\\", "/")
    if "featurelifted" in blob or "/tmp" in blob or "submission/" in blob:
        return looks_mutating(command) or "<<" in command
    return looks_mutating(command) and ("repo/" in blob or "/flb/workspace" in blob)


@dataclass
class UniqueSnapshot:
    index: int
    tree_hash: str
    tokens: int | None
    n_files: int
    n_bytes: int
    source: str
    path: str | None = None


@dataclass
class ReplayResult:
    task_id: str
    unique: list[UniqueSnapshot]
    last_hash: str | None
    disk_hash: str | None
    last_matches_disk: bool
    total_tokens: int
    editor_writes: int
    terminal_runs: int
    terminal_errors: int
    files: dict[str, bytes] = field(default_factory=dict)
    error: str | None = None


class WorkspaceSandbox:
    def __init__(self, repo_src: Path) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="flb-replay-"))
        self.workspace = self.home / "workspace"
        self.tmp = self.home / "tmp"
        self.workspace.mkdir()
        self.tmp.mkdir()
        (self.workspace / "submission").mkdir()
        dest_repo = self.workspace / "repo"
        shutil.copytree(repo_src, dest_repo, symlinks=True, dirs_exist_ok=False)
        self.pkg = self.workspace / "submission" / "featurelifted"
        self.pkg.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        shutil.rmtree(self.home, ignore_errors=True)

    def rewrite(self, command: str) -> str:
        text = command.replace("/flb/workspace", "\x00WS\x00")
        text = re.sub(r"/tmp(?=/|\s|$|\"|')", "\x00TMP\x00", text)
        return text.replace("\x00WS\x00", str(self.workspace)).replace("\x00TMP\x00", str(self.tmp))

    def apply_editor(self, path: str, content: str) -> Path | None:
        rewritten = self.rewrite(path)
        dest = Path(rewritten)
        if not str(dest).startswith(str(self.workspace)):
            rel = path.replace("\\", "/")
            marker = "/submission/"
            if marker in rel:
                dest = self.workspace / "submission" / rel.split(marker, 1)[1]
            else:
                return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content.encode("utf-8"))
        return dest

    def run_terminal(self, command: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
        rewritten = self.rewrite(command)
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["TMPDIR"] = str(self.tmp)
        env["PYTHONPATH"] = str(self.workspace / "submission")
        return subprocess.run(
            ["bash", "-lc", rewritten],
            cwd=self.workspace,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )


def replay_events(
    *,
    events_path: Path,
    repo_src: Path,
    audit_path: Path | None = None,
    keep_files: bool = True,
    save_hashes: set[str] | None = None,
    save_root: Path | None = None,
) -> ReplayResult:
    task_id = events_path.parent.parent.name
    calls = load_billed_calls(audit_path) if audit_path else []
    total_tokens = calls[-1][2] if calls else 0
    sandbox = WorkspaceSandbox(repo_src)
    unique: list[UniqueSnapshot] = []
    seen: set[str] = set()
    last_action: dict[str, Any] | None = None
    save_hashes = save_hashes or set()
    editor_writes = 0
    terminal_runs = 0
    terminal_errors = 0
    last_hash: str | None = None
    files: dict[str, bytes] = {}
    try:
        for event in iter_jsonl(events_path):
            kind = event.get("kind")
            if kind == "ActionEvent":
                last_action = event
                continue
            if kind != "ObservationEvent":
                continue
            observation = event.get("observation") if isinstance(event.get("observation"), dict) else {}
            ts = parse_ts(event.get("timestamp"))
            tokens = tokens_at(calls, ts)
            tool = str(event.get("tool_name") or "")
            mutated = False
            source = tool
            path_label: str | None = None
            if tool == "file_editor":
                if observation.get("is_error"):
                    continue
                command = str(observation.get("command") or "")
                if command not in EDITOR_WRITE_COMMANDS:
                    continue
                new_content = observation.get("new_content")
                if not isinstance(new_content, str):
                    continue
                path = str(observation.get("path") or "")
                if sandbox.apply_editor(path, new_content) is not None:
                    editor_writes += 1
                    mutated = True
                    source = f"editor:{command}"
                    path_label = path
            elif tool in {"terminal", "bash", "execute_bash"}:
                action = last_action.get("action") if isinstance(last_action, dict) else {}
                command = str((action or {}).get("command") or "")
                if observation.get("is_error") or not should_run_terminal(command):
                    continue
                terminal_runs += 1
                try:
                    completed = sandbox.run_terminal(command)
                except (subprocess.TimeoutExpired, OSError):
                    terminal_errors += 1
                    continue
                if completed.returncode != 0:
                    terminal_errors += 1
                mutated = True
                source = "terminal"
                path_label = command[:160]
            if not mutated:
                continue
            files = package_files(sandbox.pkg)
            digest = tree_hash(files) if files else ""
            last_hash = digest or last_hash
            if not files or digest in seen:
                continue
            seen.add(digest)
            unique.append(
                UniqueSnapshot(
                    index=len(unique),
                    tree_hash=digest,
                    tokens=tokens,
                    n_files=len(files),
                    n_bytes=sum(len(blob) for blob in files.values()),
                    source=source,
                    path=path_label,
                )
            )
            if save_root is not None and digest in save_hashes:
                write_tree(save_root / digest / "featurelifted", files)
        files = package_files(sandbox.pkg) if keep_files else files
        last_hash = tree_hash(files) if files else last_hash
        if save_root is not None and last_hash and last_hash in save_hashes:
            write_tree(save_root / last_hash / "featurelifted", files)
    finally:
        sandbox.close()
    return ReplayResult(
        task_id=task_id,
        unique=unique,
        last_hash=last_hash,
        disk_hash=None,
        last_matches_disk=False,
        total_tokens=total_tokens,
        editor_writes=editor_writes,
        terminal_runs=terminal_runs,
        terminal_errors=terminal_errors,
        files=files,
    )


def attach_disk_hash(result: ReplayResult, submission_pkg: Path) -> ReplayResult:
    disk = package_files(submission_pkg)
    result.disk_hash = tree_hash(disk) if disk else None
    result.last_matches_disk = bool(
        result.last_hash and result.disk_hash and result.last_hash == result.disk_hash
    )
    return result


def sample_unique(
    unique: list[UniqueSnapshot],
    *,
    extra: int = 2,
) -> list[UniqueSnapshot]:
    if not unique:
        return []
    chosen: dict[str, UniqueSnapshot] = {
        "first": unique[0],
        "last": unique[-1],
    }
    for mark in TOKEN_MARKS:
        hit = next((item for item in unique if item.tokens is not None and item.tokens >= mark), None)
        if hit is not None:
            chosen[f"ge_{mark}"] = hit
    remaining = [item for item in unique if item.tree_hash not in {row.tree_hash for row in chosen.values()}]
    if remaining and extra > 0:
        step = max(1, len(remaining) / (extra + 1))
        for index in range(1, extra + 1):
            pick = remaining[min(len(remaining) - 1, int(step * index) - 1)]
            chosen[f"extra_{index}"] = pick
    ordered = []
    seen: set[str] = set()
    for item in unique:
        if item.tree_hash in {row.tree_hash for row in chosen.values()} and item.tree_hash not in seen:
            ordered.append(item)
            seen.add(item.tree_hash)
    return ordered


def resolve_replay_repo(task_run_dir: Path, tasks_root: Path) -> Path:
    workspace_repo = task_run_dir / "workspace" / "repo"
    if workspace_repo.is_dir() and any(workspace_repo.iterdir()):
        return workspace_repo
    fallback = tasks_root / task_run_dir.name / "repo"
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError(f"no replay repo for {task_run_dir.name}")


def original_scores(task_run_dir: Path) -> dict[str, Any]:
    path = task_run_dir / "eval" / "result.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    return {
        "functional_gate": scores.get("functional_gate"),
        "build_pass": payload.get("build_pass"),
        "public_tests_pass": payload.get("public_tests_pass"),
        "hidden_tests_pass": payload.get("hidden_tests_pass"),
        "isolation_pass": payload.get("isolation_pass"),
    }


def score_tuple(result: dict[str, Any]) -> dict[str, Any]:
    scores = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    return {
        "functional_gate": scores.get("functional_gate"),
        "build_pass": result.get("build_pass"),
        "public_tests_pass": result.get("public_tests_pass"),
        "hidden_tests_pass": result.get("hidden_tests_pass"),
        "isolation_pass": result.get("isolation_pass"),
    }


def earliest_pass(rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    passed = [row for row in rows if row.get("functional_gate") == 1.0]
    if not passed:
        return None
    return min(passed, key=lambda row: (row.get("tokens") is None, row.get("tokens") or 0, row.get("index") or 0))
