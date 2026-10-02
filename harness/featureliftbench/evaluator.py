"""Evaluator entry points."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dependency_install import install_dependency_lock
from .eval_config import EVAL_PYTEST_VERSION
from .checks import find_forbidden_dependencies
from .checks import find_forbidden_imports
from .checks import read_forbidden_imports
from .compactness import analyze_submission_footprint
from .metadata import load_metadata
from .metrics import count_files
from .metrics import count_python_loc
from .metrics import count_runtime_dependencies
from .metrics import count_suspicious_files
from .metrics import dependency_name
from .metrics import directory_size_bytes
from .isolation_checks import find_isolation_attack_patterns
from .scoring import functional_gate
from .scoring import score_submission
from .source_archive import materialize_task_source
from .resource_limits import command_result_resource_fields
from .resource_limits import eval_memory_limit_mb
from .resource_limits import run_captured_command
from .validate import validate_runnable_task


@dataclass(frozen=True)
class CommandResult:
    """Subprocess command result captured by the evaluator."""

    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False
    skipped: bool = False
    reason: str = ""
    resource_limited: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    log_limit_exceeded: bool = False

    @property
    def passed(self) -> bool:
        return self.skipped or (
            self.returncode == 0
            and not self.timed_out
            and not self.resource_limited
            and not self.log_limit_exceeded
        )


def evaluate_submission(
    task_dir: str | Path,
    submission_dir: str | Path,
    output_dir: str | Path,
    *,
    functional_only: bool = False,
    trusted_capsule: bool = False,
    isolation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a submission and write ``result.json`` under ``output_dir``."""

    if _task_language(task_dir) == "go":
        from .go_evaluator import evaluate_go_submission

        return evaluate_go_submission(task_dir, submission_dir, output_dir)
    return _evaluate_python_submission(
        task_dir,
        submission_dir,
        output_dir,
        functional_only=functional_only,
        trusted_capsule=trusted_capsule,
        isolation_context=isolation_context,
    )


def _evaluate_python_submission(
    task_dir: str | Path,
    submission_dir: str | Path,
    output_dir: str | Path,
    *,
    functional_only: bool = False,
    trusted_capsule: bool = False,
    isolation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a submission and write ``result.json`` under ``output_dir``."""

    task_path = Path(task_dir).resolve()
    try:
        language = load_metadata(task_path).data.get("language", "python")
    except Exception:
        language = "python"
    if language == "go":
        from .go_eval import evaluate_go_submission

        return evaluate_go_submission(task_dir, submission_dir, output_dir)

    submission_path = Path(submission_dir).resolve()
    output_path = Path(output_dir).resolve()
    logs_path = output_path / "logs"
    output_path.mkdir(parents=True, exist_ok=True)
    logs_path.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    validation = None if trusted_capsule else validate_runnable_task(task_path)
    if validation is not None and not validation.valid:
        errors.extend(f"invalid task: {error}" for error in validation.errors)

    if not submission_path.exists():
        errors.append(f"submission dir not found: {submission_path}")
    elif not submission_path.is_dir():
        errors.append(f"submission path is not a directory: {submission_path}")

    try:
        metadata = load_metadata(task_path).data
    except Exception:
        metadata = {}
    fallback_task_id = validation.task_id if validation is not None else task_path.name
    task_id = (
        metadata.get("task_id", fallback_task_id)
        if isinstance(metadata, dict)
        else fallback_task_id
    )
    submission_name = submission_path.name

    source_repo = task_path / "repo"
    if _is_relative_to(submission_path, source_repo):
        errors.append("submission must not be inside the task repo directory")

    forbidden_names = _load_forbidden_names(task_path, metadata)
    forbidden_issues = (
        find_forbidden_imports(submission_path, forbidden_names)
        if submission_path.exists() and submission_path.is_dir()
        else []
    )
    forbidden_dependency_names = _forbidden_dependency_names(metadata)
    forbidden_dependency_issues = (
        find_forbidden_dependencies(submission_path, forbidden_dependency_names)
        if submission_path.exists() and submission_path.is_dir()
        else []
    )
    isolation_attack_issues = (
        find_isolation_attack_patterns(submission_path)
        if submission_path.exists() and submission_path.is_dir()
        else []
    )
    forbidden_imports_pass = not forbidden_issues
    forbidden_dependencies_pass = not forbidden_dependency_issues
    static_isolation_pass = not isolation_attack_issues
    forbidden_runtime_capabilities_pass = static_isolation_pass
    runtime_audit_events: list[str] = []
    submission_location_pass = not _is_relative_to(submission_path, source_repo)
    original_import_pass = (
        forbidden_imports_pass
        and forbidden_dependencies_pass
        and forbidden_runtime_capabilities_pass
        and submission_location_pass
    )
    errors.extend(issue.format(submission_path) for issue in forbidden_issues)
    errors.extend(issue.format() for issue in forbidden_dependency_issues)
    errors.extend(issue.format() for issue in isolation_attack_issues)

    metrics = _collect_metrics(submission_path, source_repo=source_repo)

    environment_info: dict[str, str] = {
        "venv_dir": "",
        "python": "",
        "install_mode": "not-run",
    }
    dependency_install_result = None
    eval_tooling_result = None
    submission_install_result = None
    build_result = None
    public_result = None
    hidden_result = None
    build_pass = False
    test_pass = False
    public_tests_pass = False
    hidden_tests_pass = False

    if submission_path.exists() and submission_path.is_dir():
        timeout_seconds = _timeout_seconds(metadata)
        with tempfile.TemporaryDirectory(prefix="featureliftbench-eval-") as tmp:
            run_cwd = Path(tmp)
            venv_dir = run_cwd / ".venv"
            venv_python = _venv_python(venv_dir)
            runtime_submission_path = run_cwd / "submission-runtime"
            try:
                shutil.copytree(submission_path, runtime_submission_path, symlinks=True)
            except OSError as exc:
                errors.append(f"submission runtime copy failed: {exc}")
            environment_info["venv_dir"] = str(venv_dir)
            environment_info["python"] = str(venv_python)
            environment_info["runtime_submission_dir"] = str(runtime_submission_path)
            output_package = _output_package(metadata)
            isolation_audit_log = run_cwd / "isolation-audit.log"
            import_guard_dir = _write_import_guard(
                run_cwd=run_cwd,
                output_package=output_package,
                allowed_roots=[runtime_submission_path, venv_dir],
                forbidden_imports=forbidden_names,
                isolation_audit_log=isolation_audit_log,
            )

            venv_python, venv_result, eval_tooling_result, venv_errors = _prepare_eval_venv(
                run_cwd=run_cwd,
                venv_dir=venv_dir,
                logs_path=logs_path,
                timeout_seconds=timeout_seconds,
            )
            errors.extend(venv_errors)

            if (
                runtime_submission_path.is_dir()
                and venv_python is not None
                and eval_tooling_result is not None
                and eval_tooling_result.passed
            ):
                base_env = _base_evaluation_env()
                dependency_install_result = _install_dependency_lock(
                    venv_python=venv_python,
                    task_path=task_path,
                    metadata=metadata,
                    cwd=run_cwd,
                    env=base_env,
                    timeout_seconds=timeout_seconds,
                )
                _write_command_logs(logs_path, "dependency_install", dependency_install_result)
                if not dependency_install_result.passed:
                    errors.append("dependency installation failed")

                submission_install_result, install_mode = _install_submission(
                    venv_python=venv_python,
                    submission_path=runtime_submission_path,
                    output_package=output_package,
                    cwd=run_cwd,
                    env=base_env,
                    timeout_seconds=timeout_seconds,
                )
                environment_info["install_mode"] = install_mode
                _write_command_logs(logs_path, "submission_install", submission_install_result)
                if not submission_install_result.passed:
                    errors.append("submission installation failed")

                if dependency_install_result.passed and submission_install_result.passed:
                    env = _evaluation_env(
                        runtime_submission_path if install_mode in {"path", "path-fallback"} else None,
                        import_guard_dir=import_guard_dir,
                    )
                    build_result = _run_import_check(
                        python=venv_python,
                        package=output_package,
                        cwd=run_cwd,
                        env=env,
                        timeout_seconds=timeout_seconds,
                        expected_root=runtime_submission_path if install_mode == "editable" else None,
                    )
                    _write_command_logs(logs_path, "build", build_result)

                    if (
                        not build_result.passed
                        and install_mode == "editable"
                        and _has_direct_output_package(runtime_submission_path, output_package)
                    ):
                        fallback_env = _evaluation_env(
                            runtime_submission_path,
                            import_guard_dir=import_guard_dir,
                        )
                        fallback_build_result = _run_import_check(
                            python=venv_python,
                            package=output_package,
                            cwd=run_cwd,
                            env=fallback_env,
                            timeout_seconds=timeout_seconds,
                        )
                        _write_command_logs(logs_path, "build_fallback", fallback_build_result)
                        if fallback_build_result.passed:
                            install_mode = "path-fallback"
                            environment_info["install_mode"] = install_mode
                            env = fallback_env
                            build_result = fallback_build_result

                    build_pass = build_result.passed

                    if build_pass:
                        public_result = _run_pytest(
                            python=venv_python,
                            test_path=task_path / _test_path(metadata, "public", "public_tests/"),
                            cwd=run_cwd,
                            env=env,
                            timeout_seconds=timeout_seconds,
                        )
                        _write_command_logs(logs_path, "public", public_result)

                        hidden_result = _run_pytest(
                            python=venv_python,
                            test_path=task_path / _test_path(metadata, "hidden", "hidden_tests/"),
                            cwd=run_cwd,
                            env=env,
                            timeout_seconds=timeout_seconds,
                        )
                        _write_command_logs(logs_path, "hidden", hidden_result)

                        public_tests_pass = public_result.passed
                        hidden_tests_pass = hidden_result.passed
                        test_pass = public_tests_pass and hidden_tests_pass
                        if public_result.resource_limited:
                            errors.append("public tests exceeded memory limit")
                        if hidden_result.resource_limited:
                            errors.append("hidden tests exceeded memory limit")
            if isolation_audit_log.is_file():
                runtime_audit_events = [
                    line
                    for line in isolation_audit_log.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                    if line.strip()
                ]

    boundary = isolation_context or {}
    forbidden_runtime_capabilities_pass = (
        static_isolation_pass and not runtime_audit_events
    )
    original_import_pass = (
        forbidden_imports_pass
        and forbidden_dependencies_pass
        and forbidden_runtime_capabilities_pass
        and submission_location_pass
    )
    errors.extend(
        f"runtime isolation audit blocked: {event}" for event in runtime_audit_events
    )
    source_filesystem_absent = bool(
        boundary.get("source_filesystem_absent", not functional_only)
    )
    network_disabled = bool(boundary.get("network_disabled", not functional_only))
    mount_allowlist_pass = bool(boundary.get("mount_allowlist_pass", not functional_only))
    runtime_import_origin_pass = bool(build_result and build_result.passed)
    isolation_pass = all(
        (
            forbidden_imports_pass,
            forbidden_dependencies_pass,
            forbidden_runtime_capabilities_pass,
            runtime_import_origin_pass,
            source_filesystem_absent,
            network_disabled,
            submission_location_pass,
            mount_allowlist_pass,
        )
    )
    isolation = {
        "pass": isolation_pass,
        "forbidden_imports_pass": forbidden_imports_pass,
        "forbidden_dependencies_pass": forbidden_dependencies_pass,
        "forbidden_runtime_capabilities_pass": forbidden_runtime_capabilities_pass,
        "runtime_audit_pass": not runtime_audit_events,
        "runtime_audit_events": runtime_audit_events,
        "runtime_import_origin_pass": runtime_import_origin_pass,
        "source_filesystem_absent": source_filesystem_absent,
        "network_disabled": network_disabled,
        "submission_location_pass": submission_location_pass,
        "mount_allowlist_pass": mount_allowlist_pass,
        "verification_mode": str(
            boundary.get(
                "verification_mode",
                "functional_capsule_pending_host_verification"
                if functional_only
                else "local_development_compatibility_not_for_paper",
            )
        ),
    }
    gate = functional_gate(
        build_pass=build_pass,
        public_tests_pass=public_tests_pass,
        hidden_tests_pass=hidden_tests_pass,
        isolation_pass=isolation_pass,
    )
    compactness: dict[str, Any] = {
        "status": "unavailable",
        "reason": "submission directory is missing",
    }
    if functional_only:
        compactness = {
            "status": "not_run",
            "reason": "functional container cannot access source or reference data",
        }
    elif submission_path.is_dir():
        try:
            with tempfile.TemporaryDirectory(
                prefix="featureliftbench-source-metrics-"
            ) as source_tmp:
                full_source = Path(source_tmp) / "repo"
                provenance = materialize_task_source(
                    str(task_id),
                    full_source,
                    require_registered=_is_python_main_task(task_path),
                )
                compactness = analyze_submission_footprint(
                    task_path,
                    submission_path,
                    source_path=(
                        full_source if provenance is not None else source_repo
                    ),
                    functional_pass=bool(gate),
                )
                compactness["status"] = "ok"
                compactness["source_provenance"] = provenance or {
                    "snapshot_scope": "task_local"
                }
                reference_loc = compactness.get("reference_loc")
                if isinstance(reference_loc, int):
                    metrics["reference_loc"] = reference_loc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            compactness = {
                "status": "error",
                "reason": f"{type(exc).__name__}: {exc}",
            }
            errors.append(f"compactness analysis failed: {exc}")
    scores = score_submission(
        metrics=metrics,
        metadata=metadata,
        functional_gate_score=gate,
    )

    result: dict[str, Any] = {
        "task_id": task_id,
        "submission": submission_name,
        "status": "passed" if gate else "failed",
        "build_pass": build_pass,
        "public_tests_pass": public_tests_pass,
        "hidden_tests_pass": hidden_tests_pass,
        "isolation_pass": isolation_pass,
        "isolation": isolation,
        "test_pass": test_pass,
        "original_import_pass": original_import_pass,
        "evaluation_capsule_digest": str(boundary.get("evaluation_capsule_digest", "")),
        "compactness_status": str(compactness.get("status", "unavailable")),
        "environment": environment_info,
        "dependency_install": _command_result_payload(dependency_install_result),
        "eval_tooling": _command_result_payload(eval_tooling_result),
        "submission_install": _command_result_payload(submission_install_result),
        "build": _command_result_payload(build_result),
        "public_tests": _command_result_payload(public_result),
        "hidden_tests": _command_result_payload(hidden_result),
        "metrics": metrics,
        "compactness": compactness,
        "scores": scores,
        "logs": {
            "dir": str(logs_path),
        },
        "errors": errors,
    }

    result_path = output_path / "result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def attach_compactness_metrics(
    result: dict[str, Any],
    task_dir: str | Path,
    submission_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Attach private static metrics after functional execution has ended.

    This function deliberately performs no import, package installation,
    pytest invocation, or submission subprocess.  It only reads files through
    the compactness analyzer and may therefore access source/reference data
    without exposing those data to untrusted code.
    """

    task_path = Path(task_dir).resolve()
    submission_path = Path(submission_dir).resolve()
    output_path = Path(output_dir).resolve()
    metadata = load_metadata(task_path).data
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        metrics = _collect_metrics(submission_path, source_repo=task_path / "repo")
        result["metrics"] = metrics
    errors = result.get("errors")
    if not isinstance(errors, list):
        errors = []
        result["errors"] = errors

    compactness: dict[str, Any]
    if not submission_path.is_dir():
        compactness = {
            "status": "unavailable",
            "reason": "submission directory is missing",
        }
    else:
        try:
            with tempfile.TemporaryDirectory(
                prefix="featureliftbench-source-metrics-"
            ) as source_tmp:
                full_source = Path(source_tmp) / "repo"
                provenance = materialize_task_source(
                    str(result.get("task_id") or task_path.name),
                    full_source,
                    require_registered=_is_python_main_task(task_path),
                )
                compactness = analyze_submission_footprint(
                    task_path,
                    submission_path,
                    source_path=full_source if provenance is not None else task_path / "repo",
                    functional_pass=bool(result.get("scores", {}).get("functional_gate", 0.0)),
                )
                compactness["status"] = "ok"
                compactness["execution_policy"] = "static_read_only_no_submission_execution"
                compactness["source_provenance"] = provenance or {
                    "snapshot_scope": "task_local"
                }
                reference_loc = compactness.get("reference_loc")
                if isinstance(reference_loc, int):
                    metrics["reference_loc"] = reference_loc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            compactness = {
                "status": "error",
                "reason": f"{type(exc).__name__}: {exc}",
                "execution_policy": "static_read_only_no_submission_execution",
            }
            errors.append(f"compactness analysis failed: {exc}")

    functional_score = float(
        result.get("scores", {}).get(
            "functional_gate",
            functional_gate(
                build_pass=bool(result.get("build_pass")),
                public_tests_pass=bool(result.get("public_tests_pass")),
                hidden_tests_pass=bool(result.get("hidden_tests_pass")),
                isolation_pass=bool(result.get("isolation_pass")),
            ),
        )
    )
    result["compactness"] = compactness
    result["compactness_status"] = str(compactness.get("status", "unavailable"))
    result["scores"] = score_submission(
        metrics=metrics,
        metadata=metadata,
        functional_gate_score=functional_score,
    )
    result_path = output_path / "result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _is_python_main_task(task_path: Path) -> bool:
    return (
        task_path.parent.name == "tasks"
        and task_path.parent.parent.name == "benchmark"
        and (task_path / "metadata.json").is_file()
    )


def _load_forbidden_names(task_path: Path, metadata: dict[str, Any]) -> list[str]:
    names: list[str] = []
    forbidden_file = task_path / "evaluation" / "forbidden_imports.txt"
    if forbidden_file.exists():
        names.extend(read_forbidden_imports(forbidden_file))

    environment = metadata.get("environment")
    if isinstance(environment, dict):
        forbidden_imports = environment.get("forbidden_imports")
        if isinstance(forbidden_imports, list):
            names.extend(item for item in forbidden_imports if isinstance(item, str))

    deduped: list[str] = []
    for name in names:
        if name not in deduped:
            deduped.append(name)
    return deduped


def _task_language(task_dir: str | Path) -> str:
    try:
        metadata = load_metadata(task_dir).data
    except Exception:
        return "python"
    language = metadata.get("language")
    return language if isinstance(language, str) else "python"


def _forbidden_dependency_names(metadata: dict[str, Any]) -> list[str]:
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return []
    forbidden_dependencies = environment.get("forbidden_dependencies")
    if not isinstance(forbidden_dependencies, list):
        return []
    return [item for item in forbidden_dependencies if isinstance(item, str)]


def _collect_metrics(submission_path: Path, *, source_repo: Path) -> dict[str, int]:
    source_loc = count_python_loc(source_repo) if source_repo.exists() else 0
    if not submission_path.exists() or not submission_path.is_dir():
        return {
            "file_count": 0,
            "loc": 0,
            "source_loc": source_loc,
            "package_bytes": 0,
            "dependency_count": 0,
            "suspicious_file_count": 0,
        }

    return {
        "file_count": count_files(submission_path),
        "loc": count_python_loc(submission_path),
        "source_loc": source_loc,
        "package_bytes": directory_size_bytes(submission_path),
        "dependency_count": count_runtime_dependencies(submission_path),
        "suspicious_file_count": count_suspicious_files(submission_path),
    }


def _timeout_seconds(metadata: dict[str, Any]) -> int:
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        value = environment.get("timeout_seconds")
        if isinstance(value, int) and value > 0:
            return value
    return 60


def _output_package(metadata: dict[str, Any]) -> str:
    output = metadata.get("output")
    if isinstance(output, dict):
        package = output.get("package")
        if isinstance(package, str) and package:
            return package
    return "featurelifted"


def _test_path(metadata: dict[str, Any], key: str, default: str) -> str:
    tests = metadata.get("tests")
    if isinstance(tests, dict):
        value = tests.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def _base_evaluation_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Freeze locale-, timezone-, and hash-sensitive behavior across reruns.
    # C.UTF-8 is present in the pinned Linux evaluation image and keeps UTF-8
    # semantics without inheriting host locale state.
    env["PYTHONHASHSEED"] = "0"
    env["TZ"] = "UTC"
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    return env


def _evaluation_env(
    submission_path: Path | None,
    *,
    import_guard_dir: Path | None = None,
) -> dict[str, str]:
    env = _base_evaluation_env()
    pythonpath_entries: list[str] = []
    if import_guard_dir is not None:
        pythonpath_entries.append(str(import_guard_dir))
    if submission_path is not None:
        pythonpath_entries.append(str(submission_path))
    if pythonpath_entries:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def _write_import_guard(
    *,
    run_cwd: Path,
    output_package: str,
    allowed_roots: list[Path],
    forbidden_imports: list[str],
    isolation_audit_log: Path,
) -> Path:
    """Install sitecustomize with import-origin and runtime capability guards."""

    guard_dir = run_cwd / "_featureliftbench_import_guard"
    guard_dir.mkdir(parents=True, exist_ok=True)
    top_level = output_package.split(".", 1)[0]
    allowed = [str(path.resolve()) for path in allowed_roots]
    forbidden = sorted({name for name in forbidden_imports if name})
    forbidden_paths = (
        "/workspace/tasks",
        "/workspace/benchmark/sources",
        "/workspace/benchmark/references",
        "/workspace/submissions",
        "reference_solution",
        "compactness.json",
        "source_registry",
    )
    (guard_dir / "sitecustomize.py").write_text(
        (
            "from __future__ import annotations\n"
            "import os\n"
            "import sys\n\n"
            f"_PACKAGE = {top_level!r}\n"
            f"_ALLOWED_ROOTS = {allowed!r}\n\n"
            f"_SUBMISSION_ROOT = {str(allowed_roots[0].resolve())!r}\n"
            f"_FORBIDDEN_IMPORTS = {forbidden!r}\n"
            f"_FORBIDDEN_PATHS = {forbidden_paths!r}\n"
            f"_AUDIT_LOG = {str(isolation_audit_log)!r}\n"
            "_BLOCKED_EVENTS = {\n"
            "    'subprocess.Popen', 'os.system', 'os.posix_spawn',\n"
            "    'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo',\n"
            "    'urllib.Request',\n"
            "}\n\n"
            "def _is_relative_to(path: str, root: str) -> bool:\n"
            "    try:\n"
            "        return os.path.commonpath([path, root]) == root\n"
            "    except ValueError:\n"
            "        return False\n\n"
            "def _entry_defines_package(entry: str) -> bool:\n"
            "    if not entry:\n"
            "        return False\n"
            "    package_dir = os.path.join(entry, _PACKAGE)\n"
            "    module_file = os.path.join(entry, _PACKAGE + '.py')\n"
            "    return os.path.isfile(os.path.join(package_dir, '__init__.py')) or os.path.isfile(module_file)\n\n"
            "def _entry_allowed(entry: str) -> bool:\n"
            "    real = os.path.realpath(entry)\n"
            "    return any(_is_relative_to(real, root) for root in _ALLOWED_ROOTS)\n\n"
            "sys.path[:] = [\n"
            "    entry for entry in sys.path\n"
            "    if not (_entry_defines_package(entry) and not _entry_allowed(entry))\n"
            "]\n\n"
            "def _record(event: str, detail: object) -> None:\n"
            "    text = str(detail).replace('\\n', ' ')[:500]\n"
            "    with open(_AUDIT_LOG, 'a', encoding='utf-8') as handle:\n"
            "        handle.write(f'{event}: {text}\\n')\n\n"
            "def _forbidden_import(name: str) -> bool:\n"
            "    return any(name == item or name.startswith(item + '.') for item in _FORBIDDEN_IMPORTS)\n\n"
            "def _originates_from_submission() -> bool:\n"
            "    try:\n"
            "        frame = sys._getframe(2)\n"
            "    except ValueError:\n"
            "        return False\n"
            "    while frame is not None:\n"
            "        filename = os.path.realpath(frame.f_code.co_filename)\n"
            "        if _is_relative_to(filename, _SUBMISSION_ROOT):\n"
            "            return True\n"
            "        frame = frame.f_back\n"
            "    return False\n\n"
            "def _audit(event: str, args: tuple[object, ...]) -> None:\n"
            "    path_event = event in {'open', 'os.listdir', 'os.scandir'}\n"
            "    if event != 'import' and event not in _BLOCKED_EVENTS and not path_event:\n"
            "        return\n"
            "    from_submission = _originates_from_submission()\n"
            "    if event == 'import' and args and from_submission and _forbidden_import(str(args[0])):\n"
            "        _record(event, args[0])\n"
            "        raise PermissionError(f'forbidden upstream import: {args[0]}')\n"
            "    if event in _BLOCKED_EVENTS and from_submission:\n"
            "        _record(event, args[:2])\n"
            "        raise PermissionError(f'blocked evaluation capability: {event}')\n"
            "    if path_event and args and from_submission:\n"
            "        path = str(args[0])\n"
            "        lowered = path.lower()\n"
            "        if any(item.lower() in lowered for item in _FORBIDDEN_PATHS):\n"
            "            _record(event, path)\n"
            "            raise PermissionError(f'blocked evaluator-private path: {path}')\n\n"
            "sys.addaudithook(_audit)\n"
        ),
        encoding="utf-8",
    )
    return guard_dir


def _prepare_eval_venv(
    *,
    run_cwd: Path,
    venv_dir: Path,
    logs_path: Path,
    timeout_seconds: int,
) -> tuple[Path | None, CommandResult | None, CommandResult | None, list[str]]:
    """Create an eval venv and ensure pytest is available (retry once on failure)."""

    errors: list[str] = []
    last_venv_result: CommandResult | None = None
    last_tooling_result: CommandResult | None = None

    for attempt in range(2):
        if attempt > 0 and venv_dir.exists():
            shutil.rmtree(venv_dir, ignore_errors=True)

        venv_suffix = "" if attempt == 0 else "_retry"
        tooling_suffix = "" if attempt == 0 else "_retry"

        last_venv_result = _create_venv(
            venv_dir=venv_dir,
            cwd=run_cwd,
            timeout_seconds=timeout_seconds,
        )
        _write_command_logs(logs_path, f"venv{venv_suffix}", last_venv_result)
        if not last_venv_result.passed:
            continue

        venv_python = _venv_python(venv_dir)
        last_tooling_result = _ensure_eval_tooling(
            venv_python=venv_python,
            cwd=run_cwd,
            env=_base_evaluation_env(),
            timeout_seconds=timeout_seconds,
        )
        _write_command_logs(logs_path, f"eval_tooling{tooling_suffix}", last_tooling_result)
        if last_tooling_result.passed:
            return venv_python, last_venv_result, last_tooling_result, errors

    if last_venv_result is not None and not last_venv_result.passed:
        errors.append("venv creation failed")
    else:
        errors.append(
            f"eval tooling failed: pytest is not available in evaluation venv "
            f"(expected pytest=={EVAL_PYTEST_VERSION})"
        )
    return None, last_venv_result, last_tooling_result, errors


def _ensure_eval_tooling(
    *,
    venv_python: Path,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> CommandResult:
    version_check = _run_pytest_version_check(
        venv_python=venv_python,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if version_check.passed:
        return version_check

    install_result = _run_command(
        [
            str(venv_python),
            "-B",
            "-m",
            "pip",
            "install",
            f"pytest=={EVAL_PYTEST_VERSION}",
        ],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if not install_result.passed:
        install_result = CommandResult(
            returncode=install_result.returncode,
            duration_seconds=install_result.duration_seconds,
            stdout=install_result.stdout,
            stderr=install_result.stderr,
            timed_out=install_result.timed_out,
            reason=(
                f"failed to install pytest=={EVAL_PYTEST_VERSION} in evaluation venv"
            ),
        )
        return install_result

    return _run_pytest_version_check(
        venv_python=venv_python,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )


def _run_pytest_version_check(
    *,
    venv_python: Path,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> CommandResult:
    result = _run_command(
        [str(venv_python), "-B", "-m", "pytest", "--version"],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if result.passed:
        return result
    return CommandResult(
        returncode=result.returncode,
        duration_seconds=result.duration_seconds,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
        reason="pytest is not available in evaluation venv",
    )


def _create_venv(
    *,
    venv_dir: Path,
    cwd: Path,
    timeout_seconds: int,
) -> CommandResult:
    return _run_command(
        [sys.executable, "-B", "-m", "venv", "--system-site-packages", str(venv_dir)],
        cwd=cwd,
        env=_base_evaluation_env(),
        timeout_seconds=timeout_seconds,
    )


def _install_dependency_lock(
    *,
    venv_python: Path,
    task_path: Path,
    metadata: dict[str, Any],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> CommandResult:
    result = install_dependency_lock(
        venv_python=venv_python,
        task_path=task_path,
        metadata=metadata,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if result.skipped:
        return _skipped_command_result(result.reason)
    if result.passed:
        return CommandResult(
            returncode=0,
            duration_seconds=0.0,
            stdout=result.stdout,
            stderr=result.stderr,
            reason=result.reason,
        )
    reason = result.reason or "dependency install failed"
    if result.stderr.strip():
        reason = f"{reason}: {result.stderr.strip()}"
    return CommandResult(
        returncode=result.returncode if result.returncode is not None else 1,
        duration_seconds=0.0,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.returncode is None,
        reason=reason,
    )


def _install_submission(
    *,
    venv_python: Path,
    submission_path: Path,
    output_package: str,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> tuple[CommandResult, str]:
    if not (submission_path / "pyproject.toml").is_file():
        return _skipped_command_result("submission has no pyproject.toml; using PYTHONPATH"), "path"

    if _has_direct_output_package(submission_path, output_package) and not _force_editable_install(env):
        return (
            _skipped_command_result(
                "submission has direct output package; skipped editable install and using PYTHONPATH"
            ),
            "path-fallback",
        )

    result = _run_command(
        [
            str(venv_python),
            "-B",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "-e",
            str(submission_path),
        ],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if not result.passed and _has_direct_output_package(submission_path, output_package):
        return (
            CommandResult(
                returncode=0,
                duration_seconds=result.duration_seconds,
                stdout=result.stdout,
                stderr=result.stderr,
                reason="editable install failed; using PYTHONPATH fallback",
                skipped=True,
            ),
            "path-fallback",
        )
    return result, "editable"


def _force_editable_install(env: dict[str, str]) -> bool:
    value = env.get("FEATURELIFTBENCH_EVAL_FORCE_EDITABLE", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_direct_output_package(submission_path: Path, output_package: str) -> bool:
    top_level = output_package.split(".", 1)[0]
    return (
        (submission_path / top_level / "__init__.py").is_file()
        or (submission_path / f"{top_level}.py").is_file()
    )


def _run_import_check(
    *,
    python: Path,
    package: str,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    expected_root: Path | None = None,
) -> CommandResult:
    if expected_root is None:
        code = f"import {package}"
    else:
        root = str(expected_root.resolve())
        code = (
            f"import {package} as _m; import os; "
            f"_path = getattr(_m, '__file__', None); "
            f"assert _path, 'package has no __file__'; "
            f"_real = os.path.realpath(_path); "
            f"_root = os.path.realpath({root!r}); "
            f"assert _real == _root or _real.startswith(_root + os.sep), (_real, _root)"
        )
    return _run_command(
        [str(python), "-B", "-c", code],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )


def _run_pytest(
    *,
    python: Path,
    test_path: Path,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    memory_mb: int | None = None,
) -> CommandResult:
    limit = memory_mb if memory_mb is not None else eval_memory_limit_mb()
    return _run_command(
        [str(python), "-B", "-m", "pytest", str(test_path), "--maxfail=1", "-q"],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        memory_mb=limit,
    )


def _ensure_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    memory_mb: int | None = None,
) -> CommandResult:
    captured = run_captured_command(
        command,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        memory_mb=memory_mb,
    )
    extra = command_result_resource_fields(captured)
    return CommandResult(
        returncode=captured.returncode,
        duration_seconds=captured.duration_seconds,
        stdout=captured.stdout,
        stderr=captured.stderr,
        timed_out=captured.timed_out,
        resource_limited=captured.resource_limited,
        stdout_truncated=captured.stdout_truncated,
        stderr_truncated=captured.stderr_truncated,
        log_limit_exceeded=captured.log_limit_exceeded,
        reason=extra.get("reason", ""),
    )


def _write_command_logs(logs_path: Path, name: str, result: CommandResult) -> None:
    (logs_path / f"{name}.stdout").write_text(_ensure_text(result.stdout), encoding="utf-8")
    (logs_path / f"{name}.stderr").write_text(_ensure_text(result.stderr), encoding="utf-8")


def _command_result_payload(result: CommandResult | None) -> dict[str, Any]:
    if result is None:
        return {
            "returncode": None,
            "passed": False,
            "duration_seconds": 0.0,
            "timed_out": False,
            "skipped": False,
            "resource_limited": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
            "log_limit_exceeded": False,
            "reason": "",
        }
    return {
        "returncode": result.returncode,
        "passed": result.passed,
        "duration_seconds": round(result.duration_seconds, 6),
        "timed_out": result.timed_out,
        "skipped": result.skipped,
        "resource_limited": result.resource_limited,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        "log_limit_exceeded": result.log_limit_exceeded,
        "reason": result.reason,
    }


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _skipped_command_result(reason: str) -> CommandResult:
    return CommandResult(
        returncode=0,
        duration_seconds=0.0,
        stdout="",
        stderr="",
        skipped=True,
        reason=reason,
    )


def _failed_command_result(message: str) -> CommandResult:
    return CommandResult(
        returncode=1,
        duration_seconds=0.0,
        stdout="",
        stderr=message,
        reason=message,
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
