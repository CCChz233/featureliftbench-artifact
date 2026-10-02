"""Select upstream test files related to the target feature."""

from __future__ import annotations

import re
from pathlib import Path

from .common import DEFAULT_MAX_TEST_FILES
from .common import DEMOTE_TEST_SUBSTR
from .common import keywords_from_public_spec
from .common import source_entrypoint_names


_TEST_NAME_RE = re.compile(r"(^test_.*\.py$|.*_test\.py$)", re.IGNORECASE)

# Performance/benchmark files often mention every public symbol and previously
# outranked focused behavioral tests.
_EXTRA_DEMOTE = (
    "shell_completion",
    "completion",
    "terminal",
    "termui",
    "/benchmarks/",
    "test_benchmark",
)


def select_upstream_tests(
    repo_dir: str | Path,
    public_spec: dict | None,
    *,
    max_files: int = DEFAULT_MAX_TEST_FILES,
) -> list[str]:
    """Return repo-relative test paths ranked by keyword overlap."""

    repo = Path(repo_dir).resolve()
    if not repo.is_dir():
        return []

    keywords = [k for k in keywords_from_public_spec(public_spec) if len(k) >= 3]
    boost: set[str] = set()
    source_roots: set[str] = set()
    if isinstance(public_spec, dict):
        title = str(public_spec.get("title") or "").lower()
        if title:
            boost.add(title)
        for ep in source_entrypoint_names(public_spec):
            source_roots.add(ep.split(".", 1)[0].lower())
            for part in ep.split("."):
                if len(part) >= 3:
                    boost.add(part.lower())
    if not keywords and not boost:
        keywords = ["test"]

    demote_tokens = tuple(DEMOTE_TEST_SUBSTR) + _EXTRA_DEMOTE
    project_affinity_dirs = {
        child.name.lower()
        for child in repo.iterdir()
        if child.is_dir()
        and (child / "pyproject.toml").is_file()
        and any(
            re.sub(r"[-_.]+", "-", child.name.lower())
            == re.sub(r"[-_.]+", "-", root)
            for root in source_roots
        )
    }

    scored: list[tuple[int, str]] = []
    for path in repo.rglob("*.py"):
        if not _TEST_NAME_RE.match(path.name):
            continue
        parts = set(path.parts)
        if parts & {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox"}:
            continue
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            continue
        rel_l = rel.lower()
        demote = any(bad in rel_l for bad in demote_tokens)
        text = ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:50000].lower()
        except OSError:
            continue
        hay = f"{rel_l}\n{text}"
        score = 0
        for key in keywords:
            if key in hay:
                score += min(hay.count(key), 8)
            if key in rel_l:
                score += 30
        for key in boost:
            if key in hay:
                score += 20 + min(hay.count(key), 5)
            if key in rel_l:
                score += 40
        if "test" in path.parts or path.name.startswith("test_"):
            score += 2
        for dirname in project_affinity_dirs:
            if rel_l.startswith(dirname + "/"):
                score += 100
        if any(
            token in path.stem.lower()
            for token in (
                "revision",
                "command",
                "lazy",
                "core",
                "context",
                "evict",
                "cache",
                "defaults",
            )
        ):
            score += 8
        if demote:
            score -= 40
        if score > 0:
            scored.append((score, rel))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [rel for _, rel in scored[: max(1, int(max_files))]]
