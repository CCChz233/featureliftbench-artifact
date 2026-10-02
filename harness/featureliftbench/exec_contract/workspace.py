"""Workspace install + prompt appendices for exec_contract."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .common import CONTRACT_FAILURES
from .common import CLOSURE_CAPSULE_FILE
from .common import CONTRACTS_DIR
from .common import FACTS_FILE
from .common import RUNTIME_DIR
from .common import ensure_dir


EXEC_CONTRACT_ENV = "FEATURELIFTBENCH_EXEC_CONTRACT_PHASE"

_GENERATED_ROOT_FILES = (
    FACTS_FILE,
    "CONTRACTS.md",
    "OBLIGATIONS.json",
    "MUTATION_AUDIT.json",
    CLOSURE_CAPSULE_FILE,
    CONTRACT_FAILURES,
)


def install_exec_contract_workspace(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    submission = workspace / "submission"
    if submission.is_file() or submission.is_symlink():
        submission.unlink()
    submission.mkdir(exist_ok=True)
    ensure_dir(workspace / RUNTIME_DIR)
    ensure_dir(workspace / CONTRACTS_DIR)
    if not (workspace / FACTS_FILE).exists():
        (workspace / FACTS_FILE).write_text(
            "# Runtime Facts\n\n_(pending Phase-0 collection)_\n",
            encoding="utf-8",
        )
    return {
        "exec_contract": True,
        "runtime_dir": RUNTIME_DIR,
        "contracts_dir": CONTRACTS_DIR,
        "facts_file": FACTS_FILE,
    }


def deactivate_exec_contract_workspace(workspace_dir: str | Path) -> None:
    """Remove method-only evidence before a fail-closed Main fallback."""

    workspace = Path(workspace_dir).resolve()
    for dirname in (RUNTIME_DIR, CONTRACTS_DIR):
        path = workspace / dirname
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
    for name in _GENERATED_ROOT_FILES:
        path = workspace / name
        if path.exists() or path.is_symlink():
            path.unlink()


def phase1_task_appendix(*, variant: str = "clean3") -> str:
    variant_note = ""
    if variant in {"cgcc_lite", "cgcc_roc", "cgcc_rmc"}:
        variant_note = (
            "4. `OBLIGATIONS.json` — evidence-tiered behavior/API closure obligations.\n"
            "5. `MUTATION_AUDIT.json` — plausible omission/over-generalization "
            "families that the frozen contracts must reject.\n\n"
        )
    guidance = ""
    if variant in {"cgcc_lite", "cgcc_roc", "cgcc_rmc"}:
        guidance = (
            "7. If TASK mentions symbolic identifiers (e.g. `head` / `base`), "
            "`get_revision('head')` / `get_revision('base')` must resolve them; "
            "wiring symbols only into another method is insufficient.\n"
            "8. Treat reserved/symbolic identifiers as fallbacks: preserve an explicitly "
            "registered concrete entity with the same string.\n"
            "9. Preserve deterministic source/input order for ordered collection APIs when "
            "the upstream evidence and contracts require it.\n"
        )
    if variant in {"cgcc_roc", "cgcc_rmc"}:
        guidance += (
            "10. Keep internal graph objects separate from compact public projections. "
            "For a named alias, preserve the originally bound entity in public lookup/"
            "mapping views even when state propagates to descendants.\n"
        )
    if variant == "cgcc_rmc":
        guidance += (
            "11. Every TASK-required method named by a behavioral witness must be "
            "implemented at its boundary cases; method existence alone is insufficient.\n"
        )
    if variant == "fcec":
        variant_note = (
            f"4. `{CLOSURE_CAPSULE_FILE}` — the complete required API/signature "
            "inventory plus only runtime observations bound to public TASK clauses.\n\n"
        )
        guidance = (
            "7. Implement every required API path and published parameter/default "
            "shape before optimizing deeper behavior.\n"
            "8. Use only the clause-bound observations in the closure capsule as "
            "dynamic evidence; do not invent a broader oracle from incidental calls.\n"
        )
    return (
        "### Execution-Guided Contract — Implement from upstream runtime facts\n\n"
        "Before you start coding, this workspace already contains:\n\n"
        f"1. `{FACTS_FILE}` — observations from running **upstream `repo/` tests** "
        "(inputs/outputs/exceptions/env keys). These are ground truth, not guesses.\n"
        f"2. `{CONTRACTS_DIR}/` — executable pytest contracts targeting "
        "`submission/featurelifted`.\n"
        f"3. `{RUNTIME_DIR}/` — raw traces for reference.\n\n"
        f"{variant_note}"
        "Your job:\n"
        "1. Implement `submission/featurelifted/` per TASK.md **and** the runtime facts.\n"
        "2. Run `PYTHONPATH=submission pytest contracts/ -q` and make it **all** pass "
        "(including `test_behavior_scenarios.py` — not just surface hasattr checks).\n"
        "3. Do **not** delete/weaken contracts to force green.\n"
        "4. Do **not** import the original `repo/` package from submission.\n"
        "5. `callable(invoke)` is not enough: if scenarios call `invoke(argv)` / "
        "`resolve(argv)` / graph queries, those behaviors must work and return "
        "correct values.\n"
        "6. Prefer TASK `public_spec` signatures (e.g. optional args with defaults) "
        "over copying upstream call shapes that disagree with the TASK API.\n"
        f"{guidance}"
    )


def prepare_repair_workspace(
    workspace_dir: str | Path,
    *,
    verify_result: dict[str, Any],
    task_markdown: str,
) -> str:
    """Append contract failure feedback for a repair round."""

    workspace = Path(workspace_dir).resolve()
    body = [
        "# Contract verification failures",
        "",
        f"- ok: `{verify_result.get('ok')}`",
        f"- returncode: `{verify_result.get('returncode')}`",
        f"- backend: `{verify_result.get('backend')}`",
        "",
        "## stdout (tail)",
        "",
        "```",
        str(verify_result.get("stdout_tail") or ""),
        "```",
        "",
        "## stderr (tail)",
        "",
        "```",
        str(verify_result.get("stderr_tail") or ""),
        "```",
        "",
        "Fix `submission/featurelifted` so `PYTHONPATH=submission pytest contracts/ -q` passes.",
        "Do not weaken the contracts.",
        "",
    ]
    (workspace / CONTRACT_FAILURES).write_text("\n".join(body), encoding="utf-8")

    appendix = (
        "### Execution-Guided Contract — Repair round\n\n"
        f"Contract verification failed. See `{CONTRACT_FAILURES}`.\n"
        "Repair the submission so contracts pass; do not weaken contracts.\n"
    )
    # strip prior exec-contract appendices
    import re

    base = re.sub(
        r"\n## Execution-Guided Contract.*",
        "",
        task_markdown,
        flags=re.DOTALL,
    ).rstrip()
    new_task = base + "\n\n## Execution-Guided Contract Repair\n\n" + appendix
    (workspace / "TASK.md").write_text(new_task + "\n", encoding="utf-8")
    return new_task
