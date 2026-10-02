"""Run closure checks in the same dependency environment as the coding agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..agent_docker import DEFAULT_AGENT_IMAGE
from ..agent_docker import run_command_in_agent_docker
from .checker import check_workspace


_ISOLATED_RESULT = ".contract_closure_isolated.json"


def check_workspace_isolated(
    workspace_dir: str | Path,
    *,
    use_docker: bool,
    docker_image: str | None = None,
    check_mode: str = "full",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Check locally or in the agent image, never in an unrelated host env."""

    workspace = Path(workspace_dir).resolve()
    if not use_docker:
        result = check_workspace(workspace, check_mode=check_mode)
        result["execution_environment"] = {"backend": "local"}
        return result

    result_path = workspace / _ISOLATED_RESULT
    result_path.unlink(missing_ok=True)
    mode_arg = {
        "full": [],
        "structure": ["--structure-only"],
        "behavior": ["--behavior-only"],
        "micro": ["--micro"],
        "lite_plus": ["--lite-plus"],
    }.get(check_mode)
    if mode_arg is None:
        raise ValueError(f"unsupported contract check mode: {check_mode}")
    image = (docker_image or "").strip() or DEFAULT_AGENT_IMAGE
    command = [
        "python",
        "/flb/workspace/flb-contract-check",
        "--workspace",
        "/flb/workspace",
        "--json-out",
        f"/flb/workspace/{_ISOLATED_RESULT}",
        *mode_arg,
    ]
    completed = run_command_in_agent_docker(
        workspace,
        command,
        image=image,
        timeout_seconds=timeout_seconds,
        mount_harness=True,
    )
    try:
        if completed.returncode not in {0, 1} or not result_path.is_file():
            detail = (completed.stderr or completed.stdout or "checker failed")[-2000:]
            raise RuntimeError(
                "isolated contract checker failed "
                f"(returncode={completed.returncode}): {detail}"
            )
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("isolated contract checker returned a non-object")
        payload["execution_environment"] = {
            "backend": "agent_docker",
            "image": image,
        }
        return payload
    finally:
        result_path.unlink(missing_ok=True)
