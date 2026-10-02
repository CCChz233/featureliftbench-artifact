"""Supplementary source-evidence ablation. Isolated from Official Main.

Official Main remains ``source_context=full_repository`` with the historical
workspace, prompt, Docker mount, and ``run.json`` shape. This module is used
only when ``source_context=contract_only`` or when
``FEATURELIFTBENCH_SOURCE_ABLATION_ISOLATION`` is explicitly enabled for a
paired Full / Contract-only campaign.

See docs/paper/SUPPLEMENTARY_EXPERIMENT_RUNBOOK.md.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .ablation import AblationOptions
from .ablation import SOURCE_CONTEXT_ENV
from .task_render import render_public_task


CONTRACT_ONLY = "contract_only"
ISOLATION_ENV = "FEATURELIFTBENCH_SOURCE_ABLATION_ISOLATION"
HARNESS_MOUNT_ENV = "FEATURELIFTBENCH_AGENT_DOCKER_HARNESS_MOUNT"
VISIBLE_INVENTORY_NAME = "agent_visible_inventory.json"
HARNESS_MOUNT_FULL = "full"
HARNESS_MOUNT_PACKAGE = "package"

# Used only when supplementary isolation / contract_only hides the image harness.
# Official Main does not add these hosts.
ISOLATION_BLOCKED_HOSTS = (
    "github.com:127.0.0.1",
    "codeload.github.com:127.0.0.1",
    "raw.githubusercontent.com:127.0.0.1",
    "pypi.org:127.0.0.1",
    "pypi.python.org:127.0.0.1",
    "files.pythonhosted.org:127.0.0.1",
)

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off", ""}

CONTRACT_ONLY_RESPONSIBILITY = """Treat the requested feature as a complete task-scoped module, not as a list of isolated examples. The upstream source repository is not available in this workspace. You must implement the feature from the public behavioral contract below.

The Target API, Required Behavior, Constraints, and Exclusions below define the exhaustive scope boundary. Every obligation inside that boundary is mandatory, while unrelated upstream functionality is out of scope. Examples illustrate required semantics; they are not a small case list to fit. A submission is incomplete if it implements only the main path or passes self-written smoke tests while omitting any in-scope behavior, boundary condition, exception distinction, state transition, required member or resource, dependency, or isolation obligation."""

CONTRACT_ONLY_WORKSPACE_NOTE = """Benchmark-authored evaluator tests are not included in this workspace. The upstream source repository is not provided: there is no `repo/` snapshot, and you must not search the host, installed packages, caches, or the network for the original project. You may write and run your own tests. Do not attempt to locate evaluator tests.
"""

CONTRACT_ONLY_OPENHANDS_PUBLIC_LINE = (
    "- Benchmark-authored evaluator tests are **not mounted**. The upstream "
    "source repository is **not** available; there is no `repo/` snapshot.\n"
)
CONTRACT_ONLY_OPENHANDS_TEST_HINT = (
    "Implement from the public contract only. Do not search for the original "
    "project, its packages, or evaluator tests. You may write and run your own "
    "tests before submitting. The evaluator runs its private test tiers only "
    "after submit.\n\n"
)
CONTRACT_ONLY_OPENHANDS_SOURCE_LINE = (
    "- The upstream source repository is not present in this workspace.\n"
)


def is_contract_only(options: AblationOptions | None) -> bool:
    return bool(options is not None and options.source_context == CONTRACT_ONLY)


def agent_source_available(options: AblationOptions | None) -> bool:
    return not is_contract_only(options)


def isolation_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    raw = str(values.get(ISOLATION_ENV, "")).strip().lower()
    return raw in _TRUTHY


def records_source_ablation(
    options: AblationOptions | None,
    env: Mapping[str, str] | None = None,
) -> bool:
    return is_contract_only(options) or isolation_enabled(env)


def agent_harness_mount_mode(env: Mapping[str, str] | None = None) -> str:
    """Main default is a full harness bind-mount; supplementary isolation is package-only."""

    values = env if env is not None else os.environ
    raw = str(values.get(HARNESS_MOUNT_ENV, "")).strip().lower()
    if raw in {HARNESS_MOUNT_FULL, HARNESS_MOUNT_PACKAGE}:
        return raw
    if raw in _FALSY and raw != "":
        return HARNESS_MOUNT_FULL
    if isolation_enabled(values) or str(values.get("FEATURELIFTBENCH_SOURCE_CONTEXT", "")).strip() == CONTRACT_ONLY:
        return HARNESS_MOUNT_PACKAGE
    return HARNESS_MOUNT_FULL


def experiment_condition_fields(
    options: AblationOptions,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Extra run.json fields for the supplementary campaign. Empty for Official Main."""

    values = dict(env or {})
    values.setdefault(SOURCE_CONTEXT_ENV, options.source_context)
    if not records_source_ablation(options, values):
        return {}
    return {
        "agent_source_available": agent_source_available(options),
        "agent_harness_mount": agent_harness_mount_mode(values),
        "source_ablation_isolation": isolation_enabled(values),
    }


def render_contract_only_agent_workspace_task(
    metadata: dict[str, Any],
    *,
    mount_public_tests: bool = False,
    source_entrypoints: list[str] | None = None,
) -> str:
    """Public contract plus source-unavailable notes. Does not change Main rendering."""

    text = render_public_task(
        metadata,
        include_complete_feature_responsibility=False,
    )
    marker = "<!-- featureliftbench.complete_feature_responsibility.v1 -->"
    heading = "## Complete Feature Responsibility"
    responsibility = (
        f"{marker}\n{heading}\n\n{CONTRACT_ONLY_RESPONSIBILITY}\n\n"
    )
    # Keep the public contract ahead of the workspace note; insert responsibility
    # immediately after the summary block that render_public_task already wrote.
    text = _insert_after_summary(text, responsibility)
    if source_entrypoints:
        text += (
            "\n## Source Entrypoints — Entrypoint-Hint Ablation\n\n"
            "This diagnostic arm provides frozen upstream implementation anchors:\n\n"
            + "".join(f"- `{item}`\n" for item in source_entrypoints)
        )
    if not mount_public_tests:
        text += "\n## Agent Workspace Note\n\n" + CONTRACT_ONLY_WORKSPACE_NOTE
    return text


def contract_only_python_intro(sections: dict[str, str]) -> str:
    return (
        f"# FeatureLiftBench Task: {sections['task_id']}\n\n"
        "You are in a FeatureLiftBench agent workspace. The upstream source "
        "repository is not available. Implement the requested feature as a "
        "standalone, installable Python package under `submission/` from the "
        "public behavioral contract below.\n\n"
    )


def contract_only_python_howto(sections: dict[str, str], options: AblationOptions) -> str:
    grep = sections.get("forbidden_grep") or "original package names"
    return (
        "## How to work\n\n"
        "1. Use the functional contract and **Required Output API** to implement "
        "every listed output path in `submission/featurelifted/`.\n"
        "2. Rewrite imports so runtime code uses `featurelifted` only — never the original package.\n"
        "3. **The upstream source repository is not mounted.** Do not search for "
        "`repo/`, the original project, or evaluator tests. Write your own tests if needed.\n"
        "4. Implement against the complete public contract.\n"
        f"5. Before submitting, grep your submission for forbidden imports, e.g. "
        f"`grep -R \"import \" submission/ | grep -E '({grep})'` — any match fails evaluation.\n"
        "6. Before submitting, verify your package is under `submission/featurelifted/`, e.g. "
        "`test -d submission/featurelifted && ls submission/featurelifted | head`.\n"
        "7. Do **not** put your package in `featurelifted/` at the workspace root — only "
        "`submission/featurelifted/` counts.\n"
        "8. When confident, submit with the command at the bottom.\n\n"
    )


def contract_only_python_workspace() -> str:
    return (
        "## Workspace\n\n"
        "- The upstream source repository is not provided. There is no `repo/` directory.\n"
        "- Benchmark-authored evaluator tests are not provided. You may write and run your own tests.\n"
        "- `requirements.lock`: locked third-party runtime dependencies allowed by the task.\n"
        "- `metadata.json`: redacted task metadata. Hidden tests and evaluator internals are not present.\n"
        "- `submission/`: write your final package here.\n\n"
    )


def contract_only_closure_localization() -> str:
    return (
        "- Reconstruct the implementation from the functional contract and required "
        "output API. The upstream repository is not available in this workspace.\n"
    )


def contract_only_implementation_scope() -> str:
    return (
        "- Implementation scope: the upstream repository is not available; implement "
        "the public surface listed by the import line from the functional contract.\n\n"
    )


def openhands_contract_only_wrapper_lines() -> tuple[str, str, str]:
    return (
        CONTRACT_ONLY_OPENHANDS_SOURCE_LINE,
        CONTRACT_ONLY_OPENHANDS_PUBLIC_LINE,
        CONTRACT_ONLY_OPENHANDS_TEST_HINT,
    )


def list_visible_workspace_paths(workspace_dir: str | Path) -> list[str]:
    root = Path(workspace_dir).resolve()
    paths: list[str] = []
    if not root.is_dir():
        return paths
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part in {"__pycache__", ".git"} for part in path.relative_to(root).parts):
            continue
        paths.append(relative)
    return paths


def write_visible_workspace_inventory(
    workspace_dir: str | Path,
    output_dir: str | Path,
    *,
    options: AblationOptions,
    extra: Mapping[str, Any] | None = None,
) -> Path:
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    workspace = Path(workspace_dir).resolve()
    payload: dict[str, Any] = {
        "schema": "featureliftbench.source_ablation.workspace_inventory.v1",
        "source_context": options.source_context,
        "agent_source_available": agent_source_available(options),
        "repo_present": (workspace / "repo").exists(),
        "files": list_visible_workspace_paths(workspace),
    }
    if extra:
        payload.update(dict(extra))
    destination = output_path / VISIBLE_INVENTORY_NAME
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def assert_contract_only_workspace(workspace_dir: str | Path) -> None:
    workspace = Path(workspace_dir).resolve()
    leaks: list[str] = []
    if (workspace / "repo").exists():
        leaks.append("repo/")
    if (workspace / "public_tests").exists():
        leaks.append("public_tests/")
    if (workspace / "hidden_tests").exists():
        leaks.append("hidden_tests/")
    if (workspace / "reference_solution").exists():
        leaks.append("reference_solution/")
    if (workspace / "evaluation").exists():
        leaks.append("evaluation/")
    if leaks:
        raise ValueError(
            "contract_only workspace contains source or evaluator material: "
            + ", ".join(leaks)
        )


def _insert_after_summary(text: str, block: str) -> str:
    """Insert responsibility after the title/summary that render_public_task emits."""

    marker = "\nThe submitted implementation must not import"
    index = text.find(marker)
    if index < 0:
        return block + text
    return text[:index] + "\n" + block + text[index + 1 :]
