"""Go submission evaluator."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .checks import find_forbidden_go_imports
from .checks import read_forbidden_imports
from .evaluator import CommandResult
from .evaluator import _command_result_payload
from .evaluator import _is_relative_to
from .evaluator import _write_command_logs
from .metadata import load_metadata
from .metrics import count_files
from .metrics import count_go_loc
from .metrics import count_suspicious_files
from .metrics import directory_size_bytes
from .resource_limits import CapturedCommandResult
from .resource_limits import eval_memory_limit_mb
from .resource_limits import run_captured_command
from .scoring import functional_gate
from .scoring import score_submission
from .validate import validate_task


def evaluate_go_submission(
    task_dir: str | Path,
    submission_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate a Go submission and write ``result.json``."""

    task_path = Path(task_dir).resolve()
    submission_path = Path(submission_dir).resolve()
    output_path = Path(output_dir).resolve()
    logs_path = output_path / "logs"
    output_path.mkdir(parents=True, exist_ok=True)
    logs_path.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    validation = validate_task(task_path)
    if not validation.valid:
        errors.extend(f"invalid task: {error}" for error in validation.errors)

    if not submission_path.exists():
        errors.append(f"submission dir not found: {submission_path}")
    elif not submission_path.is_dir():
        errors.append(f"submission path is not a directory: {submission_path}")

    metadata = load_metadata(task_path).data if task_path.exists() else {}
    task_id = metadata.get("task_id", validation.task_id) if isinstance(metadata, dict) else validation.task_id
    submission_name = submission_path.name

    source_repo = task_path / "repo"
    if _is_relative_to(submission_path, source_repo):
        errors.append("submission must not be inside the task repo directory")

    forbidden_names = _load_forbidden_names(task_path, metadata)
    forbidden_issues = (
        find_forbidden_go_imports(submission_path, forbidden_names)
        if submission_path.exists() and submission_path.is_dir()
        else []
    )
    original_import_pass = not forbidden_issues and not _is_relative_to(submission_path, source_repo)
    errors.extend(issue.format(submission_path) for issue in forbidden_issues)

    metrics = _collect_go_metrics(submission_path, source_repo=source_repo)
    timeout_seconds = _timeout_seconds(metadata)
    module_path = _go_module_path(metadata)

    environment_info: dict[str, str] = {
        "go": _go_version(metadata),
        "module_path": module_path,
        "install_mode": "go-mod-replace",
    }
    build_result = None
    public_result = None
    hidden_result = None
    build_pass = False
    test_pass = False

    if submission_path.exists() and submission_path.is_dir() and not errors:
        with tempfile.TemporaryDirectory(prefix="featureliftbench-go-eval-") as tmp:
            run_cwd = Path(tmp)
            try:
                _prepare_go_workspace(
                    run_cwd=run_cwd,
                    task_path=task_path,
                    submission_path=submission_path,
                    module_path=module_path,
                )
            except OSError as exc:
                errors.append(f"go workspace setup failed: {exc}")
            else:
                cache_root = output_path / ".go-cache"
                cache_root.mkdir(parents=True, exist_ok=True)
                env = _go_evaluation_env(timeout_seconds)
                env["GOCACHE"] = str(cache_root / "build")
                env["GOMODCACHE"] = str(cache_root / "mod")
                memory_mb = eval_memory_limit_mb()
                build_result = _run_go_build(
                    cwd=run_cwd,
                    env=env,
                    timeout_seconds=timeout_seconds,
                    memory_mb=memory_mb,
                    module_path=module_path,
                )
                _write_command_logs(logs_path, "build", build_result)
                build_pass = build_result.passed
                if not build_pass:
                    errors.append("go build failed")

                public_rel = _test_path(metadata, "public", "public_tests")
                hidden_rel = _test_path(metadata, "hidden", "hidden_tests")
                public_result = _run_go_test(
                    cwd=run_cwd,
                    package_path=f"./{public_rel.rstrip('/')}",
                    env=env,
                    timeout_seconds=timeout_seconds,
                    memory_mb=memory_mb,
                )
                _write_command_logs(logs_path, "public", public_result)

                hidden_result = _run_go_test(
                    cwd=run_cwd,
                    package_path=f"./{hidden_rel.rstrip('/')}",
                    env=env,
                    timeout_seconds=timeout_seconds,
                    memory_mb=memory_mb,
                )
                _write_command_logs(logs_path, "hidden", hidden_result)
                test_pass = bool(public_result.passed and hidden_result.passed)
                if public_result.resource_limited:
                    errors.append("public tests exceeded memory limit")
                if hidden_result.resource_limited:
                    errors.append("hidden tests exceeded memory limit")

    gate = functional_gate(
        build_pass=build_pass,
        test_pass=test_pass,
        original_import_pass=original_import_pass,
    )
    scores = score_submission(
        metrics=metrics,
        metadata=metadata,
        functional_gate_score=gate,
    )

    result: dict[str, Any] = {
        "task_id": task_id,
        "submission": submission_name,
        "language": "go",
        "status": "passed" if gate else "failed",
        "build_pass": build_pass,
        "test_pass": test_pass,
        "original_import_pass": original_import_pass,
        "environment": environment_info,
        "dependency_install": _command_result_payload(None),
        "eval_tooling": _command_result_payload(build_result),
        "submission_install": _command_result_payload(build_result),
        "build": _command_result_payload(build_result),
        "public_tests": _command_result_payload(public_result),
        "hidden_tests": _command_result_payload(hidden_result),
        "metrics": metrics,
        "scores": scores,
        "logs": {"dir": str(logs_path)},
        "errors": errors,
    }
    (output_path / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _prepare_go_workspace(
    *,
    run_cwd: Path,
    task_path: Path,
    submission_path: Path,
    module_path: str,
) -> None:
    shutil.copytree(submission_path, run_cwd / "submission", symlinks=True)
    for rel in ("public_tests", "hidden_tests"):
        src = task_path / rel
        if src.is_dir():
            shutil.copytree(src, run_cwd / rel, symlinks=True)

    env_go_mod = task_path / "environment" / "go.mod"
    go_sum = task_path / "environment" / "go.sum"
    if env_go_mod.is_file():
        shutil.copy2(env_go_mod, run_cwd / "go.mod")
    else:
        (run_cwd / "go.mod").write_text(
            f"module featureliftbench/eval\n\ngo 1.22\n",
            encoding="utf-8",
        )
    if go_sum.is_file():
        shutil.copy2(go_sum, run_cwd / "go.sum")

    _patch_go_mod_replace(run_cwd / "go.mod", module_path, "./submission")
    submission_mod = run_cwd / "submission" / "go.mod"
    if submission_mod.is_file():
        _ensure_submission_module(submission_mod, module_path)


def _patch_go_mod_replace(go_mod: Path, module_path: str, replace_path: str) -> None:
    text = go_mod.read_text(encoding="utf-8")
    replace_line = f"replace {module_path} => {replace_path}"
    if "replace " in text and module_path in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    text += f"\nrequire {module_path} v0.0.0\n{replace_line}\n"
    go_mod.write_text(text, encoding="utf-8")


def _ensure_submission_module(go_mod: Path, module_path: str) -> None:
    text = go_mod.read_text(encoding="utf-8")
    if re.search(r"^module\s+", text, flags=re.MULTILINE):
        text = re.sub(r"^module\s+.+$", f"module {module_path}", text, count=1, flags=re.MULTILINE)
    else:
        text = f"module {module_path}\n\n{text}"
    go_mod.write_text(text, encoding="utf-8")


def _go_evaluation_env(timeout_seconds: int) -> dict[str, str]:
    env = os.environ.copy()
    env["CGO_ENABLED"] = "0"
    env["GOPROXY"] = "off"
    env["GOFLAGS"] = "-mod=mod"
    env["GOTRACEBACK"] = "all"
    env["GO_TEST_TIMEOUT"] = str(timeout_seconds)
    return env


def _run_go_build(
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    memory_mb: int | None,
    module_path: str,
) -> CommandResult:
    return _run_go_command(
        ["go", "build", "-mod=mod", f"./..."],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        memory_mb=memory_mb,
    )


def _run_go_test(
    *,
    cwd: Path,
    package_path: str,
    env: dict[str, str],
    timeout_seconds: int,
    memory_mb: int | None,
) -> CommandResult:
    return _run_go_command(
        ["go", "test", "-mod=mod", "-count=1", "-timeout", f"{timeout_seconds}s", package_path],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds + 10,
        memory_mb=memory_mb,
    )


def _run_go_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    memory_mb: int | None,
) -> CommandResult:
    captured = run_captured_command(
        command,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        memory_mb=memory_mb,
    )
    return _captured_to_command_result(captured)


def _captured_to_command_result(captured: CapturedCommandResult) -> CommandResult:
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


def _collect_go_metrics(submission_path: Path, *, source_repo: Path) -> dict[str, int]:
    source_loc = count_go_loc(source_repo) if source_repo.exists() else 0
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
        "loc": count_go_loc(submission_path),
        "source_loc": source_loc,
        "package_bytes": directory_size_bytes(submission_path),
        "dependency_count": _count_go_requirements(submission_path),
        "suspicious_file_count": count_suspicious_files(submission_path),
    }


def _count_go_requirements(submission_path: Path) -> int:
    go_mod = submission_path / "go.mod"
    if not go_mod.is_file():
        return 0
    count = 0
    for line in go_mod.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("require ") and " indirect" not in stripped:
            count += 1
        elif stripped == "require (":
            continue
        elif stripped and stripped[0].islower() and " " in stripped and not stripped.startswith("module "):
            if stripped.endswith(")"):
                continue
            count += 1
    return count


def _timeout_seconds(metadata: dict[str, Any]) -> int:
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        value = environment.get("timeout_seconds")
        if isinstance(value, int) and value > 0:
            return value
    return 60


def _go_module_path(metadata: dict[str, Any]) -> str:
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        module_path = environment.get("module_path")
        if isinstance(module_path, str) and module_path:
            return module_path
    output = metadata.get("output")
    if isinstance(output, dict):
        package = output.get("package")
        if isinstance(package, str) and package:
            return package
    return "featurelifted"


def _go_version(metadata: dict[str, Any]) -> str:
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        value = environment.get("go")
        if isinstance(value, str) and value:
            return value
    return "1.22"


def _test_path(metadata: dict[str, Any], key: str, default: str) -> str:
    tests = metadata.get("tests")
    if isinstance(tests, dict):
        value = tests.get(key)
        if isinstance(value, str) and value:
            return value.rstrip("/")
    return default.rstrip("/")
