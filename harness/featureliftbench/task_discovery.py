"""Shared task directory discovery for the main benchmark and sanity smoke tasks."""

from __future__ import annotations

import json
from pathlib import Path

from .paths import SANITY_TASKS_DIR, TASKS_DIR

SKIP_DIRS = frozenset({"extreme"})


def _load_difficulty(task_dir: Path) -> str | None:
    metadata_path = task_dir / "metadata.json"
    if not metadata_path.is_file():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    value = metadata.get("difficulty")
    return value if isinstance(value, str) else None


def discover_task_dirs_under(
    root: Path,
    *,
    task_ids: list[str] | None = None,
    difficulty: set[str] | None = None,
    hard_only: bool = False,
) -> list[Path]:
    """List task directories under a root (single task dir or dataset root)."""

    path = root.resolve()
    if (path / "metadata.json").is_file():
        candidates = [path]
    elif not path.is_dir():
        raise ValueError(f"task path does not exist or is not a directory: {path}")
    else:
        candidates = sorted(
            child.resolve()
            for child in path.iterdir()
            if child.name not in SKIP_DIRS and (child / "metadata.json").is_file()
        )

    if task_ids:
        allowed = set(task_ids)
        candidates = [task_dir for task_dir in candidates if task_dir.name in allowed]
        if not candidates:
            raise ValueError(f"no matching task directories for: {', '.join(sorted(allowed))}")

    if hard_only or difficulty:
        allowed_diff = difficulty or ({"hard"} if hard_only else None)
        if allowed_diff:
            candidates = [
                task_dir
                for task_dir in candidates
                if _load_difficulty(task_dir) in allowed_diff
            ]

    if not candidates:
        raise ValueError(f"no task directories found under: {path}")
    return candidates


def discover_main_task_dirs(
    input_path: str | Path | None = None,
    *,
    task_ids: list[str] | None = None,
    hard_only: bool = True,
) -> list[Path]:
    """Discover tasks for the main benchmark (benchmark/tasks/ by default)."""

    from .paths import resolve_task_input

    root = resolve_task_input(input_path) if input_path is not None else TASKS_DIR
    return discover_task_dirs_under(root, task_ids=task_ids, hard_only=hard_only)


def discover_sanity_task_dirs() -> list[Path]:
    """Discover smoke/sanity tasks under benchmark/sanity/."""

    if not SANITY_TASKS_DIR.is_dir():
        return []
    return discover_task_dirs_under(SANITY_TASKS_DIR, hard_only=False)
