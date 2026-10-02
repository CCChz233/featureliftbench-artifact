"""Quality gates for Go benchmark task promotion."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def go_no_stub_gate(
    task_id: str,
    task_dir: Path,
    *,
    repo_root: Path,
    oracle_dir: Path | None = None,
) -> dict[str, Any]:
    """Return no-stub gate details for a Go task.

    This gate is intentionally stricter than schema validation. It prevents
    hello/Add template tasks from being promoted as gold-quality Go tasks.
    """

    task_dir = Path(task_dir)
    repo_root = Path(repo_root)
    blockers: list[str] = []
    details: dict[str, Any] = {
        "task_dir": str(task_dir),
        "sanity_exempt": _is_sanity_task(task_id, task_dir),
    }

    if details["sanity_exempt"]:
        return {"passed": True, "blocking_gates": blockers, "details": details}

    repo_go_files = sorted((task_dir / "repo").rglob("*.go"))
    repo_go_rel = [str(path.relative_to(task_dir)) for path in repo_go_files]
    details["repo_go_files"] = repo_go_rel
    details["repo_go_file_count"] = len(repo_go_files)
    if not repo_go_files:
        blockers.append("G0_go_repo_empty")
    if len(repo_go_files) == 1 and repo_go_files[0].name == "add.go":
        blockers.append("G0_stub_repo_add_go")

    task_md = task_dir / "TASK.md"
    details["task_md_exists"] = task_md.is_file()
    if not task_md.is_file():
        blockers.append("G0_task_md_missing")
    else:
        task_text = task_md.read_text(encoding="utf-8", errors="replace")
        if any("hello_featurelifted__001" in line for line in task_text.splitlines()[:5]):
            blockers.append("G0_stub_task_prompt")

    design_note = repo_root / "docs" / "go_task_designs" / f"{task_id}.md"
    details["design_note"] = str(design_note)
    details["design_note_exists"] = design_note.is_file()
    if not design_note.is_file():
        blockers.append("G0_design_note_missing")

    if oracle_dir is not None and oracle_dir.is_dir():
        oracle_go_files = [
            path
            for path in sorted(oracle_dir.rglob("*.go"))
            if not _is_non_runtime_go_file(path, oracle_dir)
        ]
        details["oracle_runtime_go_file_count"] = len(oracle_go_files)
        details["oracle_runtime_go_files"] = [str(path.relative_to(oracle_dir)) for path in oracle_go_files]
        if len(oracle_go_files) < 2:
            blockers.append("G0_oracle_runtime_too_small")
        if any("func Add(" in path.read_text(encoding="utf-8", errors="replace") for path in oracle_go_files):
            blockers.append("G0_oracle_stub_add")

    return {
        "passed": not blockers,
        "blocking_gates": sorted(set(blockers)),
        "details": details,
    }


def _is_sanity_task(task_id: str, task_dir: Path) -> bool:
    return task_id == "hello_featurelifted__001" or "sanity" in task_dir.parts


def _is_non_runtime_go_file(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if path.name.endswith("_test.go"):
        return True
    if "vendor" in rel_parts:
        return True
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:256]
    except OSError:
        return True
    return "Code generated" in head and "DO NOT EDIT" in head
