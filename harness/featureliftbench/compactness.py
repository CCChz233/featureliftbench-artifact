"""Diagnostic compactness and provenance metrics for Python submissions.

These metrics intentionally remain a vector.  They are not a replacement for
the historical v1 score and the normalized-copy detector is conservative: it
only counts matching runs of at least three non-empty source lines.
"""

from __future__ import annotations

import ast
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .closure_gold import load_closure_gold
from .metrics import count_files, count_python_loc, count_runtime_dependencies
from .reference_registry import compactness_reference


_STDLIB = set(getattr(sys, "stdlib_module_names", ()))


@dataclass(frozen=True)
class _CodeFile:
    path: Path
    normalized: tuple[str, ...]


def _normalized_code_lines(path: Path) -> tuple[str, ...]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = " ".join(raw.strip().split())
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return tuple(lines)


def _python_files(root: Path) -> list[_CodeFile]:
    return [
        _CodeFile(path, _normalized_code_lines(path))
        for path in sorted(root.rglob("*.py"))
        if path.is_file()
    ]


def _copied_line_indices(
    submission_files: Iterable[_CodeFile],
    source_files: Iterable[_CodeFile],
    *,
    minimum_run: int = 3,
) -> tuple[int, dict[str, list[str]]]:
    copied = 0
    evidence: dict[str, list[str]] = {}
    sources = list(source_files)
    for submitted in submission_files:
        matched_indices: set[int] = set()
        matched_sources: set[str] = set()
        for source in sources:
            matcher = difflib.SequenceMatcher(
                None, submitted.normalized, source.normalized, autojunk=False
            )
            for block in matcher.get_matching_blocks():
                if block.size < minimum_run:
                    continue
                matched_indices.update(range(block.a, block.a + block.size))
                matched_sources.add(str(source.path))
        copied += len(matched_indices)
        if matched_sources:
            evidence[str(submitted.path)] = sorted(matched_sources)
    return copied, evidence


def _top_level_imports(root: Path) -> set[str]:
    imports: set[str] = set()
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".", 1)[0])
    return imports


def _allowed_dependencies(task_path: Path) -> set[str]:
    metadata = json.loads((task_path / "metadata.json").read_text(encoding="utf-8"))
    environment = metadata.get("environment", {})
    return {
        str(value).replace("-", "_")
        for value in environment.get("allowed_dependencies", [])
        if isinstance(value, str)
    }


def _reference_file_count(reference_path: Path) -> int | None:
    return count_files(reference_path) if reference_path.is_dir() else None


def _compactness_class(
    *,
    functional_pass: bool | None,
    extraction_ratio: float | None,
    copied_fraction: float | None,
    file_count: int,
    reference_file_count: int | None,
) -> str:
    if functional_pass is False:
        return "non_functional"
    if functional_pass is None:
        return "unclassified_without_functional_result"
    is_copy_heavy = (
        (extraction_ratio is not None and extraction_ratio >= 1.0)
        or (copied_fraction is not None and copied_fraction >= 0.80)
        or (
            reference_file_count is not None
            and reference_file_count > 0
            and file_count >= 2 * reference_file_count
        )
    )
    if is_copy_heavy:
        return "copy_heavy_pass"
    if extraction_ratio is not None and extraction_ratio <= 0.50:
        return "compact_pass"
    return "functional_mixed_footprint"


def analyze_submission_footprint(
    task_path: str | Path,
    submission_path: str | Path,
    *,
    reference_path: str | Path | None = None,
    source_path: str | Path | None = None,
    functional_pass: bool | None = None,
) -> dict[str, Any]:
    """Return the v1.1 diagnostic metric vector for one submission.

    ``excess_copied_loc`` is intentionally NA until file-level closure gold is
    complete.  Partial legacy manifests must not define an excess-copy target.
    """

    task = Path(task_path).resolve()
    submission = Path(submission_path).resolve()
    reference = (
        Path(reference_path).resolve()
        if reference_path is not None
        else (task.parents[1] / "submissions" / task.name / "oracle").resolve()
    )
    source = (
        Path(source_path).resolve()
        if source_path is not None
        else (task / "repo").resolve()
    )
    submitted_loc = count_python_loc(submission)
    frozen_reference = compactness_reference(task.name)
    reference_loc = (
        count_python_loc(reference)
        if reference.is_dir()
        else (
            frozen_reference.get("python_loc")
            if isinstance(frozen_reference, dict)
            and isinstance(frozen_reference.get("python_loc"), int)
            else None
        )
    )
    file_count = count_files(submission)
    reference_files = (
        _reference_file_count(reference)
        if reference.is_dir()
        else (
            frozen_reference.get("file_count")
            if isinstance(frozen_reference, dict)
            and isinstance(frozen_reference.get("file_count"), int)
            else None
        )
    )
    copied_loc, copy_evidence = _copied_line_indices(
        _python_files(submission), _python_files(source)
    )
    copied_fraction = copied_loc / submitted_loc if submitted_loc else 0.0
    extraction_ratio = (
        submitted_loc / reference_loc if reference_loc not in (None, 0) else None
    )

    package_roots = {path.name for path in submission.iterdir() if path.is_dir()}
    imported = _top_level_imports(submission)
    external = sorted(imported - _STDLIB - package_roots)
    allowed = _allowed_dependencies(task)
    unapproved = sorted(name for name in external if name.replace("-", "_") not in allowed)

    source_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in submission.rglob("*.py")
    )
    source_name = json.loads((task / "metadata.json").read_text(encoding="utf-8"))["source"]["name"]
    path_leakage = str(source.resolve()) in source_text or str(task.resolve()) in source_text
    forbidden_source_import = source_name.replace("-", "_") in external

    gold = load_closure_gold(task)
    file_gold_complete = gold.completeness_for("file") == "complete"

    return {
        "reference_loc": reference_loc,
        "submitted_loc": submitted_loc,
        "reference_file_count": reference_files,
        "submitted_file_count": file_count,
        "copied_file_count": len(copy_evidence),
        "copied_loc": copied_loc,
        "excess_copied_loc": None if not file_gold_complete else max(0, copied_loc - (reference_loc or 0)),
        "copied_fraction": round(copied_fraction, 6),
        "extraction_ratio_to_reference": (
            round(extraction_ratio, 6) if extraction_ratio is not None else None
        ),
        "runtime_dependency_count": count_runtime_dependencies(submission),
        "external_dependencies": external,
        "external_dependency_count": len(external),
        "unapproved_external_dependencies": unapproved,
        "unapproved_external_dependency_count": len(unapproved),
        "path_leakage": path_leakage,
        "forbidden_source_import": forbidden_source_import,
        "compactness_class": _compactness_class(
            functional_pass=functional_pass,
            extraction_ratio=extraction_ratio,
            copied_fraction=copied_fraction,
            file_count=file_count,
            reference_file_count=reference_files,
        ),
        "copy_detection": {
            "method": "normalized_nonempty_line_sequence",
            "minimum_matching_run": 3,
            "source_path": str(source),
            "evidence": copy_evidence,
            "limitations": "Conservative diagnostic heuristic; requires manual audit for paper claims.",
        },
        "closure_gold_file_completeness": gold.completeness_for("file"),
    }
