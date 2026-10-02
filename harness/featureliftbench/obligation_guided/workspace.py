"""Workspace install + prompt appendix for Obligation-Guided Feature Lifting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import LEDGER_FILE
from .ledger import build_obligation_ledger
from .ledger import ledger_has_source_leak


def install_obligation_guided_workspace(
    workspace_dir: str | Path,
    *,
    public_spec: dict[str, Any],
) -> dict[str, Any]:
    """Write the frozen public-contract ledger. Never write tests or checkers."""

    workspace = Path(workspace_dir).resolve()
    ledger = build_obligation_ledger(public_spec)
    if ledger_has_source_leak(ledger):
        raise ValueError("obligation ledger must not include source_entrypoints")
    (workspace / LEDGER_FILE).write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "obligation_guided": True,
        "ledger_file": LEDGER_FILE,
        "obligation_count": len(ledger.get("obligations") or []),
        "checker": None,
        "scenario_stubs": False,
    }


def task_appendix() -> str:
    return (
        "## Obligation-Guided Feature Lifting\n\n"
        "The harness wrote a frozen public-contract ledger in "
        f"`{LEDGER_FILE}`. Rows come only from Required Output API and the "
        "`Bxxx` clauses already in TASK.md (including isolation). This is "
        "**not** a test suite and **not** official benchmark tests.\n\n"
        "Follow this order:\n\n"
        "1. **Contract → Obligations.** Do not add, delete, split, or rename "
        "rows. Do not invent Hidden cases.\n"
        "2. **Evidence.** For each row, set `repo_evidence.path` to a file "
        "under `repo/` that implements or documents the obligation.\n"
        "3. **Implementation.** Implement the obligation in "
        "`submission/featurelifted/` and set `implementation.path` to that "
        "file.\n"
        "4. **Coverage audit before finish.** Every row must have both a "
        "repo path and an implementation path. `verification.status` may be "
        "`cited` with a path citation, or remain `?`. Path citations are "
        "coverage; self-written pytest is not.\n\n"
        "Do **not** hunt `public_tests/` or `hidden_tests/`. Do **not** run "
        "`flb-contract-check`, `run_contract_check.py`, or CGVL cells. Do "
        "**not** finish while any required row still has an empty "
        "`repo_evidence.path` or `implementation.path`.\n"
    )


def openhands_appendix() -> str:
    return (
        "Fill obligation_ledger.json from the public contract only: each row "
        "needs repo_evidence.path under repo/ and implementation.path under "
        "submission/. Do not add rows, guess Hidden tests, or treat pytest "
        "as coverage. Do not finish with empty evidence paths. Do not hunt "
        "public_tests/ or hidden_tests/."
    )
