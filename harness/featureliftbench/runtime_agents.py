"""Pinned third-party coding runtimes treated as OpenHands-level agents.

These adapters are a runtime ablation, not Official Main. Do not merge their
Functional Pass numbers into the OpenHands Python-200 leaderboard.
After ``./setup.sh``, ``dsh`` and ``codex`` resolve like ``openhands``: repo
``third_party/runtimes/bin``, then PATH, then an explicit ``agent_bin``.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .agent_adapters import AgentRunConfig
from .agent_adapters import AgentRunContext
from .paths import REPO_ROOT


RUNTIME_TASK_FILENAME = "FEATURELIFT_AGENT_TASK.md"
PINS_PATH = Path(__file__).resolve().parents[1] / "config" / "runtime_pins.json"
RUNTIME_BIN_DIR = REPO_ROOT / "third_party" / "runtimes" / "bin"

DSH_SHORT_PROMPT = (
    "Follow FEATURELIFT_AGENT_TASK.md in the current directory exactly. "
    "Extract the feature into submission/featurelifted/ and finish."
)
CODEX_SHORT_PROMPT = DSH_SHORT_PROMPT


def load_runtime_pins(path: str | Path | None = None) -> dict[str, Any]:
    pins_path = Path(path) if path is not None else PINS_PATH
    return json.loads(pins_path.read_text(encoding="utf-8"))


def runtime_task_prompt(*, task_text: str) -> str:
    """Main-protocol instructions shared by DeepSeek Harness and Codex."""

    return (
        "# FeatureLiftBench Runtime Task\n\n"
        "You are a coding agent extracting one feature from a pinned upstream "
        "repository into an independent Python package.\n\n"
        "## Information Boundary\n\n"
        "- Read `TASK.md` (authoritative public contract) and search `repo/`.\n"
        "- Benchmark-authored evaluator tests are **not mounted**. Do not look "
        "for `hidden_tests/`, `public_tests/`, `evaluation/`, or reference solutions.\n"
        "- Upstream tests, docs, and examples already present under `repo/` may "
        "be used as source context.\n"
        "- Do not access parent directories of this workspace.\n\n"
        "## Required Finish State\n\n"
        "Write the extracted package here:\n\n"
        "```text\n"
        "submission/\n"
        "  featurelifted/\n"
        "    __init__.py\n"
        "    ...\n"
        "```\n\n"
        "The evaluator installs only `submission/` after you finish. Leaving "
        "code only under `repo/` is a missing submission.\n\n"
        "## Public Contract (from TASK.md)\n\n"
        f"{task_text.rstrip()}\n"
    )


def write_runtime_task_file(context: AgentRunContext) -> Path:
    destination = context.workspace_dir / RUNTIME_TASK_FILENAME
    destination.write_text(
        runtime_task_prompt(task_text=context.task_text),
        encoding="utf-8",
    )
    return destination


def runtime_bin_dir() -> Path:
    override = os.environ.get("FEATURELIFTBENCH_RUNTIME_BIN_DIR")
    if override:
        return Path(override)
    return RUNTIME_BIN_DIR


def resolve_runtime_binary(
    config: AgentRunConfig,
    *,
    env_name: str,
    default: str,
) -> str:
    """Resolve a runtime CLI the same way OpenHands uses PATH.

    Absolute ``agent_bin`` / env overrides win (tests, custom installs). A
    bare name such as ``dsh`` prefers the repo-local pin installed by
    ``./setup.sh``, then PATH.
    """

    configured = (config.agent_bin or "").strip()
    env_value = str((config.env or {}).get(env_name) or "").strip()
    for raw in (configured, env_value):
        if raw and Path(raw).is_absolute():
            return raw
    local = _existing_executable(runtime_bin_dir() / default)
    if local:
        return local
    for raw in (configured, env_value, default):
        if not raw or Path(raw).is_absolute():
            continue
        found = _existing_executable(raw) or shutil.which(raw)
        if found:
            return found
    return configured or env_value or default


def _existing_executable(path: str | Path) -> str | None:
    resolved = Path(path)
    if resolved.is_file() and os.access(resolved, os.X_OK):
        return str(resolved.resolve())
    return None


def _resolve_bin(config: AgentRunConfig, *, env_name: str, default: str) -> str:
    return resolve_runtime_binary(config, env_name=env_name, default=default)


def build_deepseek_harness_command(
    context: AgentRunContext,
    config: AgentRunConfig,
) -> list[str]:
    del context
    binary = _resolve_bin(
        config,
        env_name="FEATURELIFTBENCH_DSH_BIN",
        default="dsh",
    )
    command = [binary, "--profile", "headless"]
    command.extend(config.extra_args)
    command.append(DSH_SHORT_PROMPT)
    return command


def build_codex_command(
    context: AgentRunContext,
    config: AgentRunConfig,
) -> list[str]:
    del context
    binary = _resolve_bin(
        config,
        env_name="FEATURELIFTBENCH_CODEX_BIN",
        default="codex",
    )
    command = [
        binary,
        "exec",
        "--approve-for-me",
        "--skip-git-repo-check",
        "--json",
    ]
    if config.model:
        command.extend(["--model", config.model])
    command.extend(config.extra_args)
    command.append(CODEX_SHORT_PROMPT)
    return command
