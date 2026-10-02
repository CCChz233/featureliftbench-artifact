"""Track and terminate in-flight agent subprocesses for suite runs."""

from __future__ import annotations

import os
import signal
import subprocess
import threading

_lock = threading.Lock()
_active_pids: set[int] = set()


def register_process(process: subprocess.Popen[object]) -> None:
    """Register a process group leader spawned for an agent run."""

    with _lock:
        _active_pids.add(process.pid)


def unregister_process(process: subprocess.Popen[object]) -> None:
    """Remove a finished agent process from the active registry."""

    with _lock:
        _active_pids.discard(process.pid)


def terminate_active_agent_processes() -> None:
    """Send SIGTERM to every active agent process group."""

    with _lock:
        pids = list(_active_pids)

    for pid in pids:
        _terminate_process_group(pid)


def _terminate_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except (PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
