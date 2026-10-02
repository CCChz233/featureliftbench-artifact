"""Shared dependency lock installation for evaluator and agent tooling."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .metrics import dependency_name
from .paths import VENDOR_WHEELS_DIR

SANITY_VENDOR_WHEELS = ("text-unidecode",)


@dataclass(frozen=True)
class DependencyInstallResult:
    skipped: bool
    passed: bool
    reason: str
    stdout: str
    stderr: str
    returncode: int | None = None


def dependency_lock_path(task_path: Path, metadata: dict[str, Any]) -> Path | None:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return None
    lock_file = environment.get("dependency_lock")
    if not isinstance(lock_file, str) or not lock_file:
        return None
    return task_path / lock_file


def dependency_names_from_lock(lock_path: Path) -> list[str]:
    names: list[str] = []
    for line in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        name = dependency_name(line)
        if name:
            names.append(name)
    return names


from .benchmark_wheels import load_benchmark_wheel_aliases


def _dependency_alias(name: str) -> str:
    normalized = dependency_name(name)
    if not normalized:
        return ""
    aliases = load_benchmark_wheel_aliases()
    return aliases.get(normalized, normalized)


def allowed_dependency_names(metadata: dict[str, Any]) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []
    allowed = environment.get("allowed_dependencies")
    if not isinstance(allowed, list):
        return []
    return [
        _dependency_alias(item)
        for item in allowed
        if isinstance(item, str) and dependency_name(item)
    ]


def forbidden_dependency_names(metadata: dict[str, Any]) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []
    forbidden = environment.get("forbidden_dependencies")
    if not isinstance(forbidden, list):
        return []
    return [item for item in forbidden if isinstance(item, str) and item]


def forbidden_dependency_names_normalized(metadata: dict[str, Any]) -> list[str]:
    return [
        dependency_name(item)
        for item in forbidden_dependency_names(metadata)
        if dependency_name(item)
    ]


def validate_lock_dependencies(metadata: dict[str, Any], dependencies: list[str]) -> list[str]:
    allowed = set(allowed_dependency_names(metadata))
    forbidden = set(forbidden_dependency_names_normalized(metadata))
    errors: list[str] = []
    not_allowed = sorted(name for name in dependencies if name not in allowed)
    forbidden_used = sorted(set(dependencies) & forbidden)
    if not_allowed:
        errors.append(
            "dependency lock contains dependencies that are not allowed: "
            + ", ".join(not_allowed)
        )
    if forbidden_used:
        errors.append(
            "dependency lock contains forbidden dependencies: " + ", ".join(forbidden_used)
        )
    return errors


def vendor_wheels_find_links() -> str | None:
    if not VENDOR_WHEELS_DIR.is_dir():
        return None
    if not any(VENDOR_WHEELS_DIR.iterdir()):
        return None
    return str(VENDOR_WHEELS_DIR.resolve())


def build_pip_install_lock_command(*, venv_python: Path, lock_path: Path) -> list[str]:
    command = [
        str(venv_python),
        "-B",
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "-r",
        str(lock_path),
    ]
    find_links = vendor_wheels_find_links()
    if find_links:
        command.extend(["--find-links", find_links])
    return command


def install_dependency_lock(
    *,
    venv_python: Path,
    task_path: Path,
    metadata: dict[str, Any],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> DependencyInstallResult:
    lock_path = dependency_lock_path(task_path, metadata)
    if lock_path is None or not lock_path.exists():
        return DependencyInstallResult(
            skipped=False,
            passed=False,
            reason=f"dependency lock file not found: {lock_path}",
            stdout="",
            stderr="",
            returncode=1,
        )

    dependencies = dependency_names_from_lock(lock_path)
    if not dependencies:
        return DependencyInstallResult(
            skipped=True,
            passed=True,
            reason="dependency lock is empty",
            stdout="",
            stderr="",
            returncode=0,
        )

    validation_errors = validate_lock_dependencies(metadata, dependencies)
    if validation_errors:
        return DependencyInstallResult(
            skipped=False,
            passed=False,
            reason="; ".join(validation_errors),
            stdout="",
            stderr="",
            returncode=1,
        )

    command = build_pip_install_lock_command(venv_python=venv_python, lock_path=lock_path)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return DependencyInstallResult(
            skipped=False,
            passed=False,
            reason=f"dependency install timed out after {timeout_seconds}s",
            stdout=stdout,
            stderr=stderr,
            returncode=None,
        )

    return DependencyInstallResult(
        skipped=False,
        passed=completed.returncode == 0,
        reason="" if completed.returncode == 0 else "dependency install failed",
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        returncode=completed.returncode,
    )


def _wheel_is_docker_compatible(filename: str) -> bool:
    lowered = filename.lower().replace("_", "-")
    if not lowered.endswith(".whl"):
        return False
    if "py3-none-any" in lowered or lowered.endswith("-any.whl"):
        return True
    if "manylinux" in lowered or "linux_" in lowered:
        return True
    return False


def vendor_wheel_present(package_name: str) -> bool:
    if not VENDOR_WHEELS_DIR.is_dir():
        return False
    normalized = package_name.lower().replace("_", "-")
    for path in VENDOR_WHEELS_DIR.iterdir():
        if not path.is_file():
            continue
        stem = path.name.lower().replace("_", "-")
        if stem.startswith(normalized + "-") and _wheel_is_docker_compatible(path.name):
            return True
    return False


def sanity_vendor_wheels_ready() -> tuple[bool, list[str]]:
    missing = [name for name in SANITY_VENDOR_WHEELS if not vendor_wheel_present(name)]
    return not missing, missing
