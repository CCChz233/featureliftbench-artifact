"""Deterministic validation for Agent-produced public evidence citations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from .schema import validate_evidence_reference


def _excerpt(path: Path, start_line: int, end_line: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines(
        keepends=True
    )
    if start_line > len(lines) or end_line > len(lines):
        raise ValueError(
            f"line range {start_line}-{end_line} exceeds {len(lines)} lines"
        )
    return "".join(lines[start_line - 1 : end_line])


def citation_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clamp_line_range(
    path: str | Path,
    start_line: int,
    end_line: int,
) -> tuple[int, int]:
    """Clamp a 1-indexed inclusive line range to the file length.

    Agents often overshoot the last line by one or two. Clamping keeps the
    citation usable while still failing empty or inverted ranges.
    """

    resolved = Path(path)
    line_count = len(
        resolved.read_text(encoding="utf-8", errors="strict").splitlines()
    )
    if line_count < 1:
        raise ValueError(f"citation file is empty: {resolved}")
    if not isinstance(start_line, int) or isinstance(start_line, bool) or start_line < 1:
        raise ValueError("start_line must be a positive integer")
    if not isinstance(end_line, int) or isinstance(end_line, bool) or end_line < 1:
        raise ValueError("end_line must be a positive integer")
    start = min(start_line, line_count)
    end = min(max(end_line, start), line_count)
    if end < start:
        raise ValueError(f"line range {start}-{end} is empty after clamping")
    return start, end


def _resolve_path(task_dir: Path, relative: str, kind: str) -> Path:
    normalized = Path(relative)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError("citation path must be relative and traversal-free")
    expected: Path
    if kind == "task":
        if normalized.as_posix() != "TASK.md":
            raise ValueError("task evidence must cite TASK.md")
        expected = task_dir / "TASK.md"
    elif kind == "public_spec":
        if normalized.as_posix() != "metadata.json":
            raise ValueError("public_spec evidence must cite metadata.json")
        expected = task_dir / "metadata.json"
    elif kind == "repository":
        if not normalized.parts or normalized.parts[0] != "repo":
            raise ValueError("repository evidence must live under repo/")
        expected = task_dir / normalized
    else:
        raise ValueError(f"unsupported evidence kind: {kind!r}")
    task_root = task_dir.resolve()
    resolved = expected.resolve()
    if not resolved.is_relative_to(task_root):
        raise ValueError("citation resolves outside the task directory")
    return resolved


def build_citation(
    task_dir: str | Path,
    *,
    path: str,
    kind: str,
    start_line: int,
    end_line: int,
    claim: str,
    clamp: bool = True,
) -> dict[str, Any]:
    root = Path(task_dir)
    resolved = _resolve_path(root, path, kind)
    if clamp:
        start_line, end_line = clamp_line_range(resolved, start_line, end_line)
    excerpt = _excerpt(resolved, start_line, end_line)
    return {
        "path": path,
        "kind": kind,
        "start_line": start_line,
        "end_line": end_line,
        "sha256": citation_digest(excerpt),
        "quote": excerpt,
        "claim": claim,
    }


def validate_citation(
    task_dir: str | Path,
    citation: Mapping[str, Any],
) -> list[str]:
    errors = validate_evidence_reference(citation)
    if errors:
        return errors
    root = Path(task_dir)
    try:
        resolved = _resolve_path(
            root,
            str(citation["path"]),
            str(citation["kind"]),
        )
    except ValueError as exc:
        return [str(exc)]
    if not resolved.is_file():
        return [f"citation file does not exist: {citation['path']}"]
    try:
        excerpt = _excerpt(
            resolved,
            int(citation["start_line"]),
            int(citation["end_line"]),
        )
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"invalid citation excerpt: {exc}"]
    actual = citation_digest(excerpt)
    if actual != citation["sha256"]:
        errors.append(
            f"citation digest mismatch for {citation['path']}: "
            f"expected {citation['sha256']}, got {actual}"
        )
    quote = citation.get("quote")
    if quote is not None and quote != excerpt:
        errors.append(f"citation quote mismatch for {citation['path']}")
    return errors
