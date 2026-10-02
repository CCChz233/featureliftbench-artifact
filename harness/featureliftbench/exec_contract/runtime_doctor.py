"""Build a deterministic, project-declared upstream test runtime plan."""

from __future__ import annotations

import configparser
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any


_PROJECT_FILES = ("pyproject.toml", "setup.py", "setup.cfg")
_TEST_GROUP_NAMES = frozenset({"test", "tests", "testing"})


def project_root_for_tests(repo_dir: str | Path, selected: list[str]) -> Path:
    """Choose the nearest Python project containing the selected test file."""

    repo = Path(repo_dir).resolve()
    if not selected:
        return repo
    rel = str(selected[0]).split("::", 1)[0]
    candidate = (repo / rel).resolve().parent
    try:
        candidate.relative_to(repo)
    except ValueError:
        return repo
    for parent in (candidate, *candidate.parents):
        if any((parent / name).is_file() for name in _PROJECT_FILES):
            return parent
        if parent == repo:
            break
    return repo


def build_runtime_plan(
    repo_dir: str | Path,
    selected: list[str],
) -> dict[str, Any]:
    """Read standard project metadata without consulting evaluator artifacts."""

    repo = Path(repo_dir).resolve()
    project_root = project_root_for_tests(repo, selected)
    pyproject = project_root / "pyproject.toml"
    data: dict[str, Any] = {}
    errors: list[str] = []
    if pyproject.is_file():
        try:
            loaded = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"pyproject parse failed: {exc}")

    pep_project = data.get("project") if isinstance(data.get("project"), dict) else {}
    poetry = _nested_dict(data, "tool", "poetry")
    project_name = str(
        pep_project.get("name") or poetry.get("name") or project_root.name
    )

    optional = (
        pep_project.get("optional-dependencies")
        if isinstance(pep_project.get("optional-dependencies"), dict)
        else {}
    )
    extras = sorted(
        str(name)
        for name in optional
        if _is_test_extra(str(name))
    )
    poetry_extras = (
        poetry.get("extras") if isinstance(poetry.get("extras"), dict) else {}
    )
    extras.extend(
        str(name)
        for name in poetry_extras
        if _is_test_extra(str(name))
    )
    extras = sorted(set(extras))

    dependency_groups = (
        data.get("dependency-groups")
        if isinstance(data.get("dependency-groups"), dict)
        else {}
    )
    group_requirements: list[str] = []
    selected_groups = sorted(
        str(name)
        for name in dependency_groups
        if str(name).lower() in _TEST_GROUP_NAMES
    )
    for name in selected_groups:
        group_requirements.extend(
            _resolve_dependency_group(dependency_groups, name, seen=set())
        )

    poetry_requirements: list[str] = []
    poetry_groups = (
        poetry.get("group") if isinstance(poetry.get("group"), dict) else {}
    )
    poetry_group_names = [
        str(name)
        for name in poetry_groups
        if str(name).lower() in _TEST_GROUP_NAMES
    ]
    if not poetry_group_names and "dev" in poetry_groups:
        # Legacy Poetry projects commonly place pytest plugins required by
        # setup.cfg addopts only in the dev group.
        poetry_group_names = ["dev"]
    selected_poetry_groups: list[str] = []
    for name in poetry_group_names:
        group = poetry_groups.get(name)
        if not isinstance(group, dict):
            continue
        deps = group.get("dependencies")
        if not isinstance(deps, dict):
            continue
        selected_poetry_groups.append(str(name))
        for dep_name, spec in deps.items():
            requirement = _poetry_requirement(str(dep_name), spec)
            if requirement:
                poetry_requirements.append(requirement)

    # Some PEP 621 projects (notably pytest itself) publish test dependencies
    # only as a ``dev`` extra. Use it only when no test-named declaration was
    # available, avoiding broad dev environments when a narrower group exists.
    if (
        not extras
        and not selected_groups
        and not selected_poetry_groups
        and "dev" in optional
    ):
        extras = ["dev"]

    pytest_config = _nested_dict(data, "tool", "pytest", "ini_options")
    if not pytest_config:
        pytest_config = _nested_dict(data, "tool", "pytest")
    pytest_minversion = str(pytest_config.get("minversion") or "").strip()
    pytest_requirement = (
        f"pytest>={pytest_minversion}" if pytest_minversion else "pytest"
    )

    sibling_projects = _local_workspace_dependencies(
        repo,
        project_root,
        data,
    )
    try:
        root_rel = project_root.relative_to(repo).as_posix()
    except ValueError:
        root_rel = "."
    return {
        "project_root": root_rel or ".",
        "project_name": project_name,
        "project_extras": extras,
        "dependency_groups": selected_groups,
        "poetry_dependency_groups": sorted(selected_poetry_groups),
        "test_requirements": _dedupe(
            [*group_requirements, *poetry_requirements, pytest_requirement]
        ),
        "build_requirements": _build_requirements(data),
        "required_pytest_plugins": _required_pytest_plugins(
            project_root,
            data,
        ),
        "pytest_requirement": pytest_requirement,
        "sibling_projects": sibling_projects,
        "metadata_errors": errors,
    }


def _required_pytest_plugins(
    project_root: Path,
    data: dict[str, Any],
) -> list[str]:
    pytest_config = _nested_dict(data, "tool", "pytest", "ini_options")
    if not pytest_config:
        pytest_config = _nested_dict(data, "tool", "pytest")
    addopts: Any = pytest_config.get("addopts")
    tokens: list[str] = []
    if isinstance(addopts, list):
        tokens = [str(item) for item in addopts]
    elif isinstance(addopts, str):
        tokens = shlex.split(addopts, comments=True)
    if not tokens:
        setup_cfg = project_root / "setup.cfg"
        if setup_cfg.is_file():
            parser = configparser.ConfigParser()
            try:
                parser.read(setup_cfg, encoding="utf-8")
                raw = parser.get("tool:pytest", "addopts", fallback="")
                tokens = shlex.split(raw, comments=True)
            except (configparser.Error, OSError, ValueError):
                tokens = []
    plugins: list[str] = []
    for index, token in enumerate(tokens[:-1]):
        if token == "-p" and tokens[index + 1].strip():
            plugins.append(tokens[index + 1].strip())
    return _dedupe(plugins)


def _build_requirements(data: dict[str, Any]) -> list[str]:
    build_system = (
        data.get("build-system")
        if isinstance(data.get("build-system"), dict)
        else {}
    )
    requires = build_system.get("requires")
    if not isinstance(requires, list):
        return []
    return _dedupe(
        [str(item) for item in requires if isinstance(item, str)]
    )


def _is_test_extra(name: str) -> bool:
    lowered = name.lower().replace("_", "-")
    return (
        lowered in _TEST_GROUP_NAMES
        or "test" in lowered
        or "check-law" in lowered
    )


def _resolve_dependency_group(
    groups: dict[str, Any],
    name: str,
    *,
    seen: set[str],
) -> list[str]:
    if name in seen:
        return []
    seen.add(name)
    values = groups.get(name)
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
        elif isinstance(value, dict):
            included = value.get("include-group")
            if isinstance(included, str):
                out.extend(_resolve_dependency_group(groups, included, seen=seen))
    return out


def _poetry_requirement(name: str, spec: Any) -> str | None:
    if name.lower() == "python":
        return None
    requirement_name = name
    version = ""
    marker = ""
    if isinstance(spec, str):
        version = spec.strip()
    elif isinstance(spec, dict):
        extras = spec.get("extras")
        if isinstance(extras, list) and extras:
            clean = [str(item) for item in extras if str(item).strip()]
            if clean:
                requirement_name += f"[{','.join(clean)}]"
        version = str(spec.get("version") or "").strip()
        marker = str(spec.get("markers") or "").strip()
        if spec.get("path") or spec.get("git") or spec.get("url"):
            return None
    if version in {"", "*"}:
        suffix = ""
    elif version.startswith((">", "<", "=", "!", "~=")):
        suffix = version
    else:
        # Poetry caret/tilde/bare constraints are not PEP 508. The exact test
        # version is not an oracle, so install the declared package unpinned.
        suffix = ""
    result = requirement_name + suffix
    if marker:
        result += f"; {marker}"
    return result


def _local_workspace_dependencies(
    repo: Path,
    project_root: Path,
    data: dict[str, Any],
) -> list[str]:
    dependency_text = repr(data.get("build-system", {})) + repr(
        (data.get("project") or {}).get("dependencies", [])
        if isinstance(data.get("project"), dict)
        else []
    )
    normalized = re.sub(r"[-_.]+", "-", dependency_text.lower())
    out: list[str] = []
    for pyproject in sorted(repo.glob("*/pyproject.toml")):
        sibling = pyproject.parent
        if sibling == project_root:
            continue
        try:
            sibling_data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        project = (
            sibling_data.get("project")
            if isinstance(sibling_data.get("project"), dict)
            else {}
        )
        name = str(project.get("name") or "")
        if not name:
            continue
        normalized_name = re.sub(r"[-_.]+", "-", name.lower())
        if normalized_name in normalized:
            out.append(sibling.relative_to(repo).as_posix())
    return out


def _nested_dict(root: dict[str, Any], *keys: str) -> dict[str, Any]:
    value: Any = root
    for key in keys:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out
