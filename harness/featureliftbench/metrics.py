"""Basic submission metrics."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


def count_python_loc(root: str | Path) -> int:
    """Count non-empty, non-comment lines in Python files under ``root``."""

    total = 0
    for path in Path(root).rglob("*.py"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                total += 1
    return total


def count_go_loc(root: str | Path) -> int:
    """Count authored Go LOC, excluding tests, vendored code, and generated files."""

    total = 0
    root_path = Path(root)
    for path in root_path.rglob("*.go"):
        if not path.is_file():
            continue
        relative = path.relative_to(root_path)
        if path.name.endswith("_test.go") or "vendor" in relative.parts:
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if any(
            line.startswith("// Code generated ") and line.endswith(" DO NOT EDIT.")
            for line in lines[:20]
        ):
            continue
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("//"):
                total += 1
    return total


def count_source_loc(root: str | Path, *, language: str = "python") -> int:
    if language == "go":
        return count_go_loc(root)
    return count_python_loc(root)


def count_files(root: str | Path) -> int:
    """Count files under ``root``."""

    return sum(1 for path in Path(root).rglob("*") if path.is_file())


def directory_size_bytes(root: str | Path) -> int:
    """Return total file size under ``root``."""

    return sum(path.stat().st_size for path in Path(root).rglob("*") if path.is_file())


def count_runtime_dependencies(root: str | Path) -> int:
    """Count declared runtime dependencies in common Python metadata files."""

    return len(find_declared_runtime_dependencies(root))


def find_declared_runtime_dependencies(root: str | Path) -> set[str]:
    """Return normalized runtime dependency names declared by a submission."""

    root_path = Path(root)
    dependencies: set[str] = set()

    pyproject = root_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            data = {}
        project = data.get("project")
        if isinstance(project, dict):
            for dependency in project.get("dependencies", []):
                if isinstance(dependency, str):
                    name = _dependency_name(dependency)
                    if name:
                        dependencies.add(name)

    for requirements_name in ("requirements.txt", "requirements.in"):
        requirements = root_path / requirements_name
        if not requirements.is_file():
            continue
        for line in requirements.read_text(encoding="utf-8", errors="ignore").splitlines():
            name = _dependency_name(line)
            if name:
                dependencies.add(name)

    return dependencies


def dependency_name(requirement: str) -> str:
    """Return a normalized dependency name from a requirement line."""

    return _dependency_name(requirement)


def count_suspicious_files(root: str | Path) -> int:
    """Count files that are usually irrelevant in an extracted runtime package."""

    root_path = Path(root)
    count = 0
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root_path)
        parts = set(relative.parts)
        name = path.name.lower()
        if parts & {".github", ".gitlab", "testing", "tests", "docs"}:
            count += 1
        elif name in {
            ".gitignore",
            ".pre-commit-config.yaml",
            "tox.ini",
            "noxfile.py",
            "uv.lock",
            "pdm.lock",
            "poetry.lock",
            "changelog",
            "readme.rst",
            "readme.md",
        }:
            count += 1
    return count


def _dependency_name(requirement: str) -> str:
    line = requirement.strip()
    if not line or line.startswith("#"):
        return ""
    if line.startswith(("-r ", "--requirement", "-c ", "--constraint")):
        return ""

    line = line.split("#", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9_.-]+)", line)
    if not match:
        return ""
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()
