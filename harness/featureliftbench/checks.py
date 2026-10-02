"""Validation checks used by the evaluator."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from .metrics import dependency_name
from .metrics import find_declared_runtime_dependencies


@dataclass(frozen=True)
class ForbiddenImportIssue:
    """A forbidden import found in a submission."""

    path: Path
    message: str
    line: int | None = None

    def format(self, root: Path) -> str:
        try:
            display_path = self.path.relative_to(root)
        except ValueError:
            display_path = self.path
        if self.line is None:
            return f"{display_path}: {self.message}"
        return f"{display_path}:{self.line}: {self.message}"


@dataclass(frozen=True)
class ForbiddenDependencyIssue:
    """A forbidden dependency declared by a submission."""

    name: str

    def format(self) -> str:
        return f"declares forbidden dependency {self.name!r}"


def read_forbidden_imports(path: str | Path) -> list[str]:
    """Read forbidden import names from a newline-delimited file."""

    names: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.append(stripped)
    return names


def find_forbidden_imports(
    root: str | Path,
    forbidden_imports: list[str],
) -> list[ForbiddenImportIssue]:
    """Statically scan a submission for forbidden import usage.

    The MVP intentionally performs static checks only. Runtime checks are harder
    to do correctly while using the host pytest installation because pytest may
    import packages such as ``iniconfig`` for its own configuration handling.
    """

    root_path = Path(root)
    forbidden = [name for name in forbidden_imports if name]
    issues: list[ForbiddenImportIssue] = []

    for path in sorted(root_path.rglob("*.py")):
        if not path.is_file():
            continue
        if _skip_static_import_scan(path, root_path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(
                ForbiddenImportIssue(
                    path=path,
                    message="cannot decode Python file as UTF-8",
                )
            )
            continue

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            issues.append(
                ForbiddenImportIssue(
                    path=path,
                    line=exc.lineno,
                    message=f"cannot parse Python file: {exc.msg}",
                )
            )
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    matched = _match_forbidden(alias.name, forbidden)
                    if matched is not None:
                        issues.append(
                            ForbiddenImportIssue(
                                path=path,
                                line=node.lineno,
                                message=f"imports forbidden module {matched!r}",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                module = node.module or ""
                matched = _match_forbidden(module, forbidden)
                if matched is not None:
                    issues.append(
                        ForbiddenImportIssue(
                            path=path,
                            line=node.lineno,
                            message=f"imports from forbidden module {matched!r}",
                        )
                    )

    return issues


def find_forbidden_dependencies(
    root: str | Path,
    forbidden_dependencies: list[str],
) -> list[ForbiddenDependencyIssue]:
    """Check declared runtime dependencies against forbidden dependency names."""

    forbidden = {_normalize_distribution_name(name) for name in forbidden_dependencies if name}
    declared = find_declared_runtime_dependencies(root)
    return [
        ForbiddenDependencyIssue(name=name)
        for name in sorted(declared & forbidden)
    ]


def _match_forbidden(module: str, forbidden: list[str]) -> str | None:
    for name in forbidden:
        if module == name or module.startswith(f"{name}."):
            return name
    return None


def _normalize_distribution_name(name: str) -> str:
    return dependency_name(name)


def find_forbidden_go_imports(
    root: str | Path,
    forbidden_imports: list[str],
) -> list[ForbiddenImportIssue]:
    """Statically scan Go source for forbidden import paths."""

    root_path = Path(root)
    forbidden = [name for name in forbidden_imports if name]
    issues: list[ForbiddenImportIssue] = []

    import_block_re = re.compile(r"import\s+\(([^)]*)\)", re.MULTILINE | re.DOTALL)
    import_single_re = re.compile(r'import\s+"([^"]+)"')
    quoted_re = re.compile(r'"([^"]+)"')

    for path in sorted(root_path.rglob("*.go")):
        if not path.is_file():
            continue
        if _skip_go_import_scan(path, root_path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(
                ForbiddenImportIssue(path=path, message="cannot decode Go file as UTF-8")
            )
            continue

        modules: list[str] = []
        for match in import_single_re.finditer(source):
            modules.append(match.group(1))
        for match in import_block_re.finditer(source):
            for imp_match in quoted_re.finditer(match.group(1)):
                modules.append(imp_match.group(1))

        for module in modules:
            matched = _match_forbidden(module, forbidden)
            if matched is not None:
                issues.append(
                    ForbiddenImportIssue(
                        path=path,
                        message=f"imports forbidden module {matched!r}",
                    )
                )

    return issues


def _skip_go_import_scan(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if relative.name.endswith("_test.go"):
        return True
    return bool(set(relative.parts) & {"vendor", ".git"})


def _skip_static_import_scan(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    name = relative.name
    if name == "test.py" or name.startswith("test_") or name.endswith("_test.py"):
        return True
    return bool(set(relative.parts) & {"tests", "testing", "docs", ".github", ".gitlab"})
