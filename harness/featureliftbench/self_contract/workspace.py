"""Workspace install + prompt appendices for self_contract."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .common import CONTRACTS_DIR
from .common import FACTS_FILE
from .common import LOCK_FILE
from .common import RUNTIME_DIR


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def install_self_contract_workspace(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    submission = workspace / "submission"
    if submission.is_file() or submission.is_symlink():
        submission.unlink()
    if submission.is_dir():
        shutil.rmtree(submission)
    submission.mkdir(exist_ok=True)
    ensure_dir(workspace / RUNTIME_DIR)
    contracts = ensure_dir(workspace / CONTRACTS_DIR)
    (contracts / "README.md").write_text(
        "# Agent-authored contracts\n\n"
        "Write executable pytest modules here that import `featurelifted`.\n"
        "Do **not** implement `submission/` in the author phase.\n",
        encoding="utf-8",
    )
    if not (workspace / FACTS_FILE).exists():
        (workspace / FACTS_FILE).write_text(
            "# Runtime Facts\n\n_(pending Phase-0 collection)_\n",
            encoding="utf-8",
        )
    return {
        "self_contract": True,
        "runtime_dir": RUNTIME_DIR,
        "contracts_dir": CONTRACTS_DIR,
        "facts_file": FACTS_FILE,
    }


def reset_submission_dir(workspace_dir: str | Path) -> None:
    """Wipe submission so implement phase starts clean after authoring."""

    workspace = Path(workspace_dir).resolve()
    submission = workspace / "submission"
    if submission.exists() or submission.is_symlink():
        if submission.is_dir() and not submission.is_symlink():
            shutil.rmtree(submission)
        else:
            submission.unlink()
    submission.mkdir(parents=True, exist_ok=True)


def author_task_appendix() -> str:
    return (
        "### Self-Authored Contract — Phase A: write contracts only\n\n"
        "This workspace contains:\n\n"
        f"1. `{FACTS_FILE}` — optional observations from upstream `repo/` tests "
        "(may be thin). Use as hints, not as finished pytest.\n"
        f"2. Empty `{CONTRACTS_DIR}/` — **you must author** executable contracts here.\n"
        "3. `repo/` — upstream source (ground truth for behavior).\n"
        "4. `TASK.md` / `public_spec` — required API and behaviors.\n\n"
        "**Your job in this phase (author only):**\n"
        f"1. Write pytest modules under `{CONTRACTS_DIR}/` that `import featurelifted` "
        "and assert real behaviors from TASK + `repo/`.\n"
        "2. Cover as many `public_spec` behaviors as you can (document mapping in "
        f"`{CONTRACTS_DIR}/README.md`).\n"
        "3. Prefer behavioral checks (call APIs, check return values / exceptions) "
        "over `hasattr`-only tests.\n"
        "4. Do **not** implement a full `submission/featurelifted` solution yet.\n"
        "5. Do **not** invent benchmark-hidden test details. Stay within TASK + repo.\n"
        "6. Forbidden: `assert True` as a passing gate; unconditional skips as the "
        "only body of a test.\n"
    )


def implement_task_appendix() -> str:
    return (
        "### Self-Authored Contract — Phase B: implement against frozen contracts\n\n"
        f"Contracts under `{CONTRACTS_DIR}/` are **frozen** (`{LOCK_FILE}`). "
        "Do not modify, delete, or weaken them.\n\n"
        "Your job:\n"
        "1. Implement `submission/featurelifted/` per TASK.md and the frozen contracts.\n"
        f"2. Make `PYTHONPATH=submission pytest {CONTRACTS_DIR}/ -q` pass.\n"
        "3. Do not import the original `repo/` package from submission.\n"
        f"4. Prefer `{FACTS_FILE}` and `repo/` when contracts are ambiguous.\n"
    )


def prepare_author_repair_workspace(
    workspace_dir: str | Path,
    *,
    gate_result: dict[str, Any],
    task_markdown: str,
) -> str:
    workspace = Path(workspace_dir).resolve()
    from .common import AUTHOR_FAILURES

    body = [
        "# Author-gate failures",
        "",
        f"- ok: `{gate_result.get('ok')}`",
        f"- errors: {gate_result.get('errors')}",
        "",
        "## Details",
        "",
        "```",
        json.dumps(gate_result, indent=2, default=str)[:4000],
        "```",
        "",
        "Revise `contracts/` only. Do not implement the full submission yet.",
        "",
    ]
    (workspace / AUTHOR_FAILURES).write_text("\n".join(body), encoding="utf-8")
    base = re.sub(
        r"\n## Self-Authored Contract.*",
        "",
        task_markdown,
        flags=re.DOTALL,
    ).rstrip()
    appendix = (
        "### Self-Authored Contract — Author repair\n\n"
        f"Author gate failed. See `{AUTHOR_FAILURES}`.\n"
        "Fix `contracts/` so the gate passes (enough real tests; empty stub must fail).\n"
    )
    new_task = base + "\n\n## Self-Authored Contract Author Repair\n\n" + appendix
    (workspace / "TASK.md").write_text(new_task + "\n", encoding="utf-8")
    return new_task


def prepare_impl_repair_workspace(
    workspace_dir: str | Path,
    *,
    verify_result: dict[str, Any],
    task_markdown: str,
) -> str:
    workspace = Path(workspace_dir).resolve()
    from .common import CONTRACT_FAILURES

    body = [
        "# Contract verification failures",
        "",
        f"- ok: `{verify_result.get('ok')}`",
        f"- returncode: `{verify_result.get('returncode')}`",
        "",
        "## stdout (tail)",
        "",
        "```",
        str(verify_result.get("stdout_tail") or ""),
        "```",
        "",
        "Fix `submission/featurelifted` only. Do not change frozen contracts.",
        "",
    ]
    (workspace / CONTRACT_FAILURES).write_text("\n".join(body), encoding="utf-8")
    base = re.sub(
        r"\n## Self-Authored Contract.*",
        "",
        task_markdown,
        flags=re.DOTALL,
    ).rstrip()
    appendix = (
        "### Self-Authored Contract — Implement repair\n\n"
        f"Verification failed. See `{CONTRACT_FAILURES}`.\n"
        "Repair submission only; contracts are frozen.\n"
    )
    new_task = base + "\n\n## Self-Authored Contract Implement Repair\n\n" + appendix
    (workspace / "TASK.md").write_text(new_task + "\n", encoding="utf-8")
    return new_task


def openhands_author_appendix() -> str:
    return (
        "Phase A only: author executable pytest under `contracts/` that import "
        "`featurelifted`. Do not implement `submission/featurelifted/` yet.\n"
        "Contracts must fail against an empty stub; no `assert True`.\n"
    )


def openhands_implement_appendix() -> str:
    return (
        "Phase B: contracts are frozen. Implement `submission/featurelifted/` so "
        "`PYTHONPATH=submission pytest contracts/ -q` passes. Do not edit `contracts/`.\n"
    )
