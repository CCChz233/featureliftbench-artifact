"""POSIX memory limits and subprocess helpers for untrusted agent/eval runs."""

from __future__ import annotations

import os
import signal
import subprocess
import sys

try:
    import resource
except ImportError:  # Windows and other non-POSIX hosts
    resource = None  # type: ignore[assignment]
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_EVAL_MEMORY_MB = 4096
DEFAULT_AGENT_MEMORY_MB = 8192
DEFAULT_COMMAND_OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024

_MEMORY_LIMIT_SUPPORTED: bool | None = None


def memory_limit_supported() -> bool:
    """Return whether this platform can lower RLIMIT_AS / RLIMIT_DATA."""

    global _MEMORY_LIMIT_SUPPORTED
    if _MEMORY_LIMIT_SUPPORTED is not None:
        return _MEMORY_LIMIT_SUPPORTED
    if resource is None or sys.platform in ("darwin", "win32"):
        _MEMORY_LIMIT_SUPPORTED = False
        return False
    probe_mb = 64
    limit = probe_mb * 1024 * 1024
    for resource_type in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
        try:
            resource.setrlimit(resource_type, (limit, limit))
            _MEMORY_LIMIT_SUPPORTED = True
            return True
        except (ValueError, OSError):
            continue
    _MEMORY_LIMIT_SUPPORTED = False
    return False


def parse_memory_limit_mb(raw: str | None) -> int | None:
    """Parse a memory limit in megabytes; 0 or negative disables the limit."""

    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    value = int(text)
    if value <= 0:
        return None
    return value


def memory_limit_mb_from_env(*names: str, default: int | None = None) -> int | None:
    for name in names:
        if name in os.environ:
            return parse_memory_limit_mb(os.environ.get(name))
    return default


def eval_memory_limit_mb() -> int | None:
    return memory_limit_mb_from_env(
        "EVAL_MEMORY_MB",
        "FEATURELIFTBENCH_EVAL_MEMORY_MB",
        default=None,
    )


def agent_memory_limit_mb(env: dict[str, str] | None = None) -> int | None:
    if env:
        for key in ("AGENT_MEMORY_MB", "FEATURELIFTBENCH_AGENT_MEMORY_MB"):
            if key in env:
                return parse_memory_limit_mb(env.get(key))
    return memory_limit_mb_from_env(
        "AGENT_MEMORY_MB",
        "FEATURELIFTBENCH_AGENT_MEMORY_MB",
        default=None,
    )


def command_output_limit_bytes(env: dict[str, str] | None = None) -> int | None:
    names = ("FEATURELIFTBENCH_COMMAND_OUTPUT_LIMIT_BYTES", "COMMAND_OUTPUT_LIMIT_BYTES")
    source = env if env is not None else os.environ
    for name in names:
        if name in source:
            return parse_memory_limit_mb(source.get(name))
    return DEFAULT_COMMAND_OUTPUT_LIMIT_BYTES


def wrap_command_with_memory_limit(command: list[str], memory_mb: int | None) -> list[str]:
    if memory_mb is None or memory_mb <= 0 or not memory_limit_supported():
        return command
    return [
        sys.executable,
        "-B",
        "-m",
        "featureliftbench.run_limited",
        str(memory_mb),
        *command,
    ]


def apply_agent_memory_limit(command: list[str], env: dict[str, str]) -> list[str]:
    return wrap_command_with_memory_limit(command, agent_memory_limit_mb(env))


def terminate_process_group(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except (AttributeError, ProcessLookupError):
        pass
    except (PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return


def detect_resource_limited(*, returncode: int, stderr: str) -> bool:
    if returncode in (-9, 137):
        return True
    text = stderr.lower()
    return "cannot allocate memory" in text or "memoryerror" in text


@dataclass(frozen=True)
class CapturedCommandResult:
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False
    resource_limited: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    log_limit_exceeded: bool = False


def run_captured_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    memory_mb: int | None = None,
    output_limit_bytes: int | None = None,
) -> CapturedCommandResult:
    """Run a command in its own process group with optional virtual-memory cap."""

    wrapped = wrap_command_with_memory_limit(command, memory_mb)
    limit = command_output_limit_bytes(env) if output_limit_bytes is None else output_limit_bytes
    if limit is not None and limit <= 0:
        limit = None
    start = time.monotonic()
    popen_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(wrapped, **popen_kwargs)
    stdout_buffer = _LimitedOutputBuffer(limit)
    stderr_buffer = _LimitedOutputBuffer(limit)
    log_limit_event = threading.Event()

    def pump(stream, buffer: "_LimitedOutputBuffer") -> None:
        assert stream is not None
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                if buffer.append(chunk) and not log_limit_event.is_set():
                    log_limit_event.set()
                    terminate_process_group(process.pid)
        finally:
            stream.close()

    threads = [
        threading.Thread(target=pump, args=(process.stdout, stdout_buffer), daemon=True),
        threading.Thread(target=pump, args=(process.stderr, stderr_buffer), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_group(process.pid)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    for thread in threads:
        thread.join(timeout=2)

    stdout = stdout_buffer.text()
    stderr = stderr_buffer.text()
    if timed_out and not stderr:
        stderr = f"command timed out after {timeout_seconds}s"
    log_limit_exceeded = log_limit_event.is_set()
    returncode = int(process.returncode or 0)
    if timed_out:
        return CapturedCommandResult(
            returncode=124,
            duration_seconds=time.monotonic() - start,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
            stdout_truncated=stdout_buffer.truncated,
            stderr_truncated=stderr_buffer.truncated,
            log_limit_exceeded=log_limit_exceeded,
        )

    stderr_text = stderr or ""
    return CapturedCommandResult(
        returncode=returncode,
        duration_seconds=time.monotonic() - start,
        stdout=stdout or "",
        stderr=stderr_text,
        resource_limited=(
            False
            if log_limit_exceeded
            else detect_resource_limited(returncode=returncode, stderr=stderr_text)
        ),
        stdout_truncated=stdout_buffer.truncated,
        stderr_truncated=stderr_buffer.truncated,
        log_limit_exceeded=log_limit_exceeded,
    )


class _LimitedOutputBuffer:
    def __init__(self, limit_bytes: int | None) -> None:
        self.limit_bytes = limit_bytes
        self.data = bytearray()
        self.truncated = False
        self._lock = threading.Lock()

    def append(self, chunk: bytes) -> bool:
        if self.limit_bytes is None:
            with self._lock:
                self.data.extend(chunk)
            return False
        remaining = max(0, self.limit_bytes - len(self.data))
        with self._lock:
            if remaining:
                self.data.extend(chunk[:remaining])
            if len(chunk) > remaining:
                self.truncated = True
                return True
        return False

    def text(self) -> str:
        with self._lock:
            raw = bytes(self.data)
        return raw.decode("utf-8", errors="replace")


def _ensure_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def command_result_resource_fields(result: CapturedCommandResult) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if result.log_limit_exceeded:
        fields["log_limit_exceeded"] = True
        fields["stdout_truncated"] = result.stdout_truncated
        fields["stderr_truncated"] = result.stderr_truncated
        fields["reason"] = "command output exceeded log limit"
    elif result.resource_limited:
        fields["resource_limited"] = True
        fields["reason"] = "memory limit exceeded"
    elif result.timed_out:
        fields["reason"] = "command timed out"
    return fields
