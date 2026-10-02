"""Resolve current and historical paths under the experiment store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT

DEFAULT_ALIAS_FILE = REPO_ROOT / "experiments" / "registry" / "path_aliases.json"


def load_path_aliases(path: Path = DEFAULT_ALIAS_FILE) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "featureliftbench.experiment_path_aliases.v1":
        raise ValueError(f"unsupported experiment path alias schema: {path}")
    aliases = payload.get("aliases")
    if not isinstance(aliases, list):
        raise ValueError(f"invalid experiment path aliases: {path}")
    return sorted(
        (item for item in aliases if isinstance(item, dict)),
        key=lambda item: len(str(item.get("old_prefix", ""))),
        reverse=True,
    )


def resolve_experiment_path(
    path: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
    alias_file: Path | None = None,
) -> Path:
    """Resolve a repository-relative historical path through longest-prefix aliases."""

    candidate = Path(path)
    absolute = candidate if candidate.is_absolute() else repo_root / candidate
    try:
        relative = absolute.resolve(strict=False).relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return absolute

    aliases = load_path_aliases(alias_file or repo_root / "experiments/registry/path_aliases.json")
    for alias in aliases:
        old_prefix = str(alias.get("old_prefix", "")).rstrip("/")
        new_prefix = str(alias.get("new_prefix", "")).rstrip("/")
        if not old_prefix or not new_prefix:
            continue
        if relative == old_prefix or relative.startswith(f"{old_prefix}/"):
            suffix = relative[len(old_prefix) :].lstrip("/")
            return repo_root / new_prefix / suffix
    return absolute
