"""Static pre-execution checks for private-path and filesystem-boundary attacks.

Merely importing modules such as ``socket`` or ``subprocess`` is not an
isolation failure: real upstream-derived features may legitimately contain
those imports in code paths that are never exercised. Runtime attempts are
blocked and recorded by the evaluator audit hook instead.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_PATH_FRAGMENTS = (
    "/workspace/tasks",
    "/workspace/benchmark/sources",
    "/workspace/benchmark/references",
    "/workspace/submissions",
    "reference_solution",
    "compactness.json",
    "source_registry",
    "source archives",
)
@dataclass(frozen=True)
class IsolationIssue:
    relative_path: str
    line: int
    reason: str

    def format(self) -> str:
        location = f"{self.relative_path}:{self.line}" if self.line else self.relative_path
        return f"{location}: isolation violation: {self.reason}"


def find_isolation_attack_patterns(submission_dir: str | Path) -> list[IsolationIssue]:
    """Find explicit source/reference paths and symlink boundary escapes."""

    root = Path(submission_dir).resolve()
    issues: list[IsolationIssue] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            issues.append(IsolationIssue(relative, 0, "symbolic links are not allowed"))
            continue
        if path.suffix != ".py" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                for fragment in FORBIDDEN_PATH_FRAGMENTS:
                    if fragment.lower() in lowered:
                        issues.append(
                            IsolationIssue(
                                relative,
                                getattr(node, "lineno", 0),
                                f"references forbidden evaluator/source path {fragment!r}",
                            )
                        )
                        break
    return _deduplicate(issues)


def _deduplicate(issues: list[IsolationIssue]) -> list[IsolationIssue]:
    seen: set[tuple[str, int, str]] = set()
    result: list[IsolationIssue] = []
    for issue in issues:
        key = (issue.relative_path, issue.line, issue.reason)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
