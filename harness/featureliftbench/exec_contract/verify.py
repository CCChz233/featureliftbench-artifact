"""Verify contracts against submission in Docker or locally."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ..agent_docker import (
    CONTAINER_WORKSPACE,
    DEFAULT_AGENT_DOCKER_CPUS,
    DEFAULT_AGENT_DOCKER_MEMORY,
    DEFAULT_AGENT_DOCKER_NETWORK,
    DEFAULT_AGENT_DOCKER_PIDS,
    DEFAULT_AGENT_DOCKER_TMPFS,
    DEFAULT_AGENT_IMAGE,
    _env_default,
    _uid_gid,
)
from .common import CONTRACTS_DIR
from .common import DEFAULT_VERIFY_TIMEOUT_SECONDS


def verify_submission_contracts(
    workspace_dir: str | Path,
    *,
    docker_image: str | None = None,
    use_docker: bool = True,
    timeout_seconds: int = DEFAULT_VERIFY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    contracts = workspace / CONTRACTS_DIR
    submission = workspace / "submission"
    result: dict[str, Any] = {
        "ok": False,
        "backend": "docker" if use_docker else "local",
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "timed_out": False,
    }
    if not contracts.is_dir():
        result["error"] = f"missing {CONTRACTS_DIR}/"
        return result
    if not submission.is_dir():
        result["error"] = "missing submission/"
        return result

    if use_docker:
        image = (docker_image or "").strip() or DEFAULT_AGENT_IMAGE
        container = f"flb-cver-{uuid.uuid4().hex[:12]}"
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container,
            "--network",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_NETWORK",
                DEFAULT_AGENT_DOCKER_NETWORK,
            ),
            "--memory",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_MEMORY",
                DEFAULT_AGENT_DOCKER_MEMORY,
            ),
            "--cpus",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_CPUS", DEFAULT_AGENT_DOCKER_CPUS
            ),
            "--pids-limit",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_PIDS", DEFAULT_AGENT_DOCKER_PIDS
            ),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_TMPFS", DEFAULT_AGENT_DOCKER_TMPFS
            ),
            "--user",
            _uid_gid(),
            "-w",
            str(CONTAINER_WORKSPACE),
            "-v",
            f"{workspace}:{CONTAINER_WORKSPACE}:rw",
            "-e",
            "PYTHONPATH=/flb/workspace/submission",
            image,
            "python",
            "-m",
            "pytest",
            f"{CONTRACTS_DIR}/",
            "-q",
            "--tb=line",
        ]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=max(1, int(timeout_seconds)),
            )
            result["returncode"] = int(proc.returncode or 0)
            result["stdout_tail"] = (proc.stdout or "")[-3000:]
            result["stderr_tail"] = (proc.stderr or "")[-3000:]
            result["ok"] = proc.returncode == 0
            result["backend"] = "docker+PYTHONPATH=submission"
        except subprocess.TimeoutExpired as exc:
            result["returncode"] = 124
            result["timed_out"] = True
            result["ok"] = False
            result["stdout_tail"] = (
                exc.stdout if isinstance(exc.stdout, str) else ""
            )[-3000:]
            result["stderr_tail"] = f"timed out after {timeout_seconds}s"
        return result

    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(contracts), "-q", "--tb=line"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        check=False,
        timeout=max(1, int(timeout_seconds)),
        env={**os.environ, "PYTHONPATH": str(submission)},
    )
    result["returncode"] = int(proc.returncode or 0)
    result["stdout_tail"] = (proc.stdout or "")[-3000:]
    result["stderr_tail"] = (proc.stderr or "")[-3000:]
    result["ok"] = proc.returncode == 0
    return result
