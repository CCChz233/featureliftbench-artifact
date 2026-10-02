"""Run evaluation inside a Docker image for reproducible baselines."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluation_capsule import build_evaluation_capsule
from .evaluator import attach_compactness_metrics
from .evaluator import evaluate_submission
from .metadata import load_metadata
from .paths import REPO_ROOT, VENDOR_WHEELS_DIR
from .reference_registry import reference_registry_path
from .source_archive import source_cache_path, source_registry_path

DEFAULT_EVAL_IMAGE = "featureliftbench-eval:latest"
DEFAULT_GO_EVAL_IMAGE = "featureliftbench-eval-go:latest"
DEFAULT_DOCKER_MEMORY = "4g"
DEFAULT_DOCKER_CPUS = "2"
DEFAULT_DOCKER_PIDS = "256"
DEFAULT_DOCKER_TMPFS = "/tmp:rw,nosuid,nodev,exec,size=2g"
DEFAULT_DOCKER_ULIMIT_NOFILE = "nofile=1024:1024"
DEFAULT_DOCKER_EVAL_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class _DockerEvalProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def evaluate_submission_docker(
    task_dir: str | Path,
    submission_dir: str | Path,
    output_dir: str | Path,
    *,
    image: str = DEFAULT_EVAL_IMAGE,
    use_docker: bool = True,
) -> dict:
    """Evaluate a submission in Docker when ``use_docker`` is True."""

    if not use_docker:
        return evaluate_submission(task_dir, submission_dir, output_dir)

    task_path = Path(task_dir).resolve()
    submission_path = Path(submission_dir).resolve()
    output_path = Path(output_dir).resolve()
    _prepare_docker_eval_output(output_path)
    image = _select_eval_image(task_path, image)
    if image != DEFAULT_GO_EVAL_IMAGE:
        return _evaluate_python_submission_docker(
            task_path=task_path,
            submission_path=submission_path,
            output_path=output_path,
            image=image,
        )
    harness_root = (REPO_ROOT / "harness").resolve()
    vendor_wheels = VENDOR_WHEELS_DIR.resolve()
    source_registry = source_registry_path()
    source_archives = source_cache_path()
    reference_registry = reference_registry_path()
    oracle_reference = (
        REPO_ROOT / "benchmark" / "submissions" / task_path.name / "oracle"
    ).resolve()
    container_name = _eval_container_name(task_path.name)

    # Task validation requires the mount basename to match metadata task_id.
    container_task = f"/workspace/tasks/{task_path.name}"
    container_submission = "/workspace/submission"
    container_output = "/workspace/output"

    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--memory",
        _env_default("FEATURELIFTBENCH_DOCKER_MEMORY", DEFAULT_DOCKER_MEMORY),
        "--memory-swap",
        _env_default(
            "FEATURELIFTBENCH_DOCKER_MEMORY_SWAP",
            _env_default("FEATURELIFTBENCH_DOCKER_MEMORY", DEFAULT_DOCKER_MEMORY),
        ),
        "--cpus",
        _env_default("FEATURELIFTBENCH_DOCKER_CPUS", DEFAULT_DOCKER_CPUS),
        "--pids-limit",
        _env_default("FEATURELIFTBENCH_DOCKER_PIDS", DEFAULT_DOCKER_PIDS),
        "--read-only",
        "--tmpfs",
        _env_default("FEATURELIFTBENCH_DOCKER_TMPFS", DEFAULT_DOCKER_TMPFS),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--ulimit",
        _env_default("FEATURELIFTBENCH_DOCKER_ULIMIT_NOFILE", DEFAULT_DOCKER_ULIMIT_NOFILE),
        "--user",
        f"{os.getuid()}:{os.getgid()}",
    ]
    for key in _forwarded_eval_env_keys():
        command.extend(["--env", key])
    command.extend(
        [
            "-v",
            f"{harness_root}:/workspace/harness:ro",
            "-v",
            f"{vendor_wheels}:/workspace/benchmark/vendor-wheels:ro",
            "-v",
            f"{source_registry}:/workspace/benchmark/sources/registry.json:ro",
            "-v",
            f"{source_archives}:/workspace/benchmark/sources/archives:ro",
            "-v",
            (
                f"{reference_registry}:"
                "/workspace/benchmark/references/compactness.json:ro"
            ),
        ]
    )
    if oracle_reference.is_dir():
        command.extend(
            [
                "-v",
                (
                    f"{oracle_reference}:/workspace/submissions/"
                    f"{task_path.name}/oracle:ro"
                ),
            ]
        )
    command.extend(
        [
            "-v",
            f"{task_path}:{container_task}:ro",
            "-v",
            f"{submission_path}:{container_submission}:ro",
            "-v",
            f"{output_path}:{container_output}:rw",
            image,
            "eval",
            container_task,
            container_submission,
            "--output",
            container_output,
        ]
    )
    timeout_seconds = _docker_eval_timeout_seconds(task_path)
    completed = _run_docker_eval(command, container_name=container_name, timeout_seconds=timeout_seconds)
    if completed.timed_out:
        return _write_docker_failure_result(
            task_path=task_path,
            submission_path=submission_path,
            output_path=output_path,
            image=image,
            command=command,
            completed=completed,
            message=f"docker eval timed out after {timeout_seconds}s",
            timed_out=True,
        )
    if completed.returncode not in {0, 1}:
        return _write_docker_failure_result(
            task_path=task_path,
            submission_path=submission_path,
            output_path=output_path,
            image=image,
            command=command,
            completed=completed,
            message="docker eval failed",
        )

    result_path = output_path / "result.json"
    if not result_path.is_file():
        return _write_docker_failure_result(
            task_path=task_path,
            submission_path=submission_path,
            output_path=output_path,
            image=image,
            command=command,
            completed=completed,
            message="docker eval did not write result.json",
        )
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _write_docker_failure_result(
            task_path=task_path,
            submission_path=submission_path,
            output_path=output_path,
            image=image,
            command=command,
            completed=completed,
            message=f"docker eval wrote invalid result.json: {exc}",
        )
    result["sandbox"] = _sandbox_payload(
        image=image,
        command=command,
        returncode=completed.returncode,
        docker_sandbox_error=False,
    )
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _evaluate_python_submission_docker(
    *,
    task_path: Path,
    submission_path: Path,
    output_path: Path,
    image: str,
) -> dict[str, Any]:
    """Run only functional evaluation in Docker, then static metrics on host."""

    harness_root = (REPO_ROOT / "harness").resolve()
    vendor_wheels = VENDOR_WHEELS_DIR.resolve()
    container_name = _eval_container_name(task_path.name)
    container_submission = "/workspace/submission"
    container_output = "/workspace/output"
    container_capsule = "/workspace/evaluation-capsule"

    with tempfile.TemporaryDirectory(prefix="featureliftbench-eval-capsule-") as tmp:
        capsule_path = Path(tmp) / "capsule"
        try:
            capsule = build_evaluation_capsule(task_path, capsule_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            completed = _DockerEvalProcessResult(
                returncode=2,
                stdout="",
                stderr=f"{type(exc).__name__}: {exc}",
            )
            return _write_docker_failure_result(
                task_path=task_path,
                submission_path=submission_path,
                output_path=output_path,
                image=image,
                command=[],
                completed=completed,
                message=f"failed to build evaluation capsule: {exc}",
            )

        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--memory",
            _env_default("FEATURELIFTBENCH_DOCKER_MEMORY", DEFAULT_DOCKER_MEMORY),
            "--memory-swap",
            _env_default(
                "FEATURELIFTBENCH_DOCKER_MEMORY_SWAP",
                _env_default("FEATURELIFTBENCH_DOCKER_MEMORY", DEFAULT_DOCKER_MEMORY),
            ),
            "--cpus",
            _env_default("FEATURELIFTBENCH_DOCKER_CPUS", DEFAULT_DOCKER_CPUS),
            "--pids-limit",
            _env_default("FEATURELIFTBENCH_DOCKER_PIDS", DEFAULT_DOCKER_PIDS),
            "--read-only",
            "--tmpfs",
            _env_default("FEATURELIFTBENCH_DOCKER_TMPFS", DEFAULT_DOCKER_TMPFS),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--ulimit",
            _env_default(
                "FEATURELIFTBENCH_DOCKER_ULIMIT_NOFILE",
                DEFAULT_DOCKER_ULIMIT_NOFILE,
            ),
            "--user",
            f"{os.getuid()}:{os.getgid()}",
        ]
        for key in _forwarded_eval_env_keys():
            command.extend(["--env", key])
        command.extend(
            [
                "-v",
                f"{harness_root}:/workspace/harness:ro",
                "-v",
                f"{vendor_wheels}:/workspace/benchmark/vendor-wheels:ro",
                "-v",
                f"{capsule_path}:{container_capsule}:ro",
                "-v",
                f"{submission_path}:{container_submission}:ro",
                "-v",
                f"{output_path}:{container_output}:rw",
                image,
                "eval",
                container_capsule,
                container_submission,
                "--output",
                container_output,
                "--functional-only",
                "--trusted-evaluation-capsule",
            ]
        )
        mount_allowlist_pass = _functional_mount_allowlist_pass(command)
        if not mount_allowlist_pass:
            completed = _DockerEvalProcessResult(
                returncode=2,
                stdout="",
                stderr="functional mount allowlist rejected generated Docker command",
            )
            return _write_docker_failure_result(
                task_path=task_path,
                submission_path=submission_path,
                output_path=output_path,
                image=image,
                command=command,
                completed=completed,
                message="functional mount allowlist rejected generated Docker command",
            )

        timeout_seconds = _docker_eval_timeout_seconds(task_path)
        completed = _run_docker_eval(
            command,
            container_name=container_name,
            timeout_seconds=timeout_seconds,
        )
        if completed.timed_out:
            return _write_docker_failure_result(
                task_path=task_path,
                submission_path=submission_path,
                output_path=output_path,
                image=image,
                command=command,
                completed=completed,
                message=f"docker eval timed out after {timeout_seconds}s",
                timed_out=True,
            )
        if completed.returncode not in {0, 1}:
            return _write_docker_failure_result(
                task_path=task_path,
                submission_path=submission_path,
                output_path=output_path,
                image=image,
                command=command,
                completed=completed,
                message="docker eval failed",
            )

        result_path = output_path / "result.json"
        if not result_path.is_file():
            return _write_docker_failure_result(
                task_path=task_path,
                submission_path=submission_path,
                output_path=output_path,
                image=image,
                command=command,
                completed=completed,
                message="docker eval did not write result.json",
            )
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _write_docker_failure_result(
                task_path=task_path,
                submission_path=submission_path,
                output_path=output_path,
                image=image,
                command=command,
                completed=completed,
                message=f"docker eval wrote invalid result.json: {exc}",
            )

    result = _finalize_functional_boundary(
        result,
        image=image,
        command=command,
        returncode=completed.returncode,
        capsule_digest=str(capsule["digest"]),
        mount_allowlist_pass=mount_allowlist_pass,
    )
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    result = attach_compactness_metrics(
        result,
        task_path,
        submission_path,
        output_path,
    )
    return result


def _functional_mount_allowlist_pass(command: list[str]) -> bool:
    allowed = {
        "/workspace/harness",
        "/workspace/benchmark/vendor-wheels",
        "/workspace/evaluation-capsule",
        "/workspace/submission",
        "/workspace/output",
    }
    targets: list[str] = []
    for index, token in enumerate(command):
        if token != "-v" or index + 1 >= len(command):
            continue
        specification = command[index + 1]
        parts = specification.rsplit(":", 2)
        if len(parts) < 2:
            return False
        targets.append(parts[-2])
    forbidden_fragments = (
        "/workspace/tasks",
        "/workspace/benchmark/sources",
        "/workspace/benchmark/references",
        "/workspace/submissions",
        "/workspace/reference_solution",
        "/workspace/oracle",
    )
    return (
        set(targets) == allowed
        and len(targets) == len(allowed)
        and not any(
            fragment in target
            for target in targets
            for fragment in forbidden_fragments
        )
    )


def _finalize_functional_boundary(
    result: dict[str, Any],
    *,
    image: str,
    command: list[str],
    returncode: int,
    capsule_digest: str,
    mount_allowlist_pass: bool,
) -> dict[str, Any]:
    isolation = result.get("isolation")
    if not isinstance(isolation, dict):
        isolation = {}
    isolation.update(
        {
            "source_filesystem_absent": mount_allowlist_pass,
            "network_disabled": "--network" in command
            and command[command.index("--network") + 1] == "none",
            "mount_allowlist_pass": mount_allowlist_pass,
            "verification_mode": "docker_functional_capsule_v1",
        }
    )
    required = (
        "forbidden_imports_pass",
        "forbidden_dependencies_pass",
        "forbidden_runtime_capabilities_pass",
        "runtime_import_origin_pass",
        "source_filesystem_absent",
        "network_disabled",
        "submission_location_pass",
        "mount_allowlist_pass",
    )
    isolation_pass = all(bool(isolation.get(key)) for key in required)
    isolation["pass"] = isolation_pass
    public_pass = bool(
        result.get(
            "public_tests_pass",
            isinstance(result.get("public_tests"), dict)
            and result["public_tests"].get("passed"),
        )
    )
    hidden_pass = bool(
        result.get(
            "hidden_tests_pass",
            isinstance(result.get("hidden_tests"), dict)
            and result["hidden_tests"].get("passed"),
        )
    )
    gate = 1.0 if all(
        (bool(result.get("build_pass")), public_pass, hidden_pass, isolation_pass)
    ) else 0.0
    scores = result.get("scores")
    if not isinstance(scores, dict):
        scores = {}
    scores["functional_gate"] = gate
    scores["final_score"] = gate
    result.update(
        {
            "status": "passed" if gate else "failed",
            "public_tests_pass": public_pass,
            "hidden_tests_pass": hidden_pass,
            "test_pass": public_pass and hidden_pass,
            "isolation_pass": isolation_pass,
            "isolation": isolation,
            "original_import_pass": isolation_pass,
            "evaluation_capsule_digest": capsule_digest,
            "compactness_status": "not_run",
            "scores": scores,
            "sandbox": _sandbox_payload(
                image=image,
                command=command,
                returncode=returncode,
                docker_sandbox_error=False,
            ),
        }
    )
    return result


def repo_root() -> Path:
    return REPO_ROOT


def _prepare_docker_eval_output(output_path: Path) -> None:
    """Prepare host output mounts for hardened eval containers.

    Eval containers use ``--read-only`` and ``--cap-drop ALL``, which prevents
    creating new directories or writing files on bind mounts that are not
    world-writable from inside the container. Pre-create and chmod the output
    tree on the host instead.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    output_path.chmod(0o777)
    logs_path = output_path / "logs"
    logs_path.mkdir(parents=True, exist_ok=True)
    logs_path.chmod(0o777)


def _run_docker_eval(
    command: list[str],
    *,
    container_name: str,
    timeout_seconds: int,
) -> _DockerEvalProcessResult:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=max(1, timeout_seconds))
        returncode = int(process.returncode or 0)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_container(container_name)
        stdout, stderr = _terminate_docker_process(process)
        returncode = 124
    return _DockerEvalProcessResult(
        returncode=returncode,
        stdout=stdout or "",
        stderr=stderr or "",
        timed_out=timed_out,
    )


def _terminate_docker_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    process.kill()
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
    return stdout or "", stderr or ""


def _kill_container(container_name: str) -> None:
    subprocess.run(
        ["docker", "kill", container_name],
        capture_output=True,
        text=True,
        check=False,
    )


def _eval_container_name(task_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", task_id)[:40]
    return f"flb-eval-{os.getpid()}-{safe}-{uuid.uuid4().hex[:8]}"


def _docker_eval_timeout_seconds(task_path: Path) -> int:
    env_raw = os.environ.get("FEATURELIFTBENCH_DOCKER_EVAL_TIMEOUT_SECONDS", "").strip()
    if env_raw:
        try:
            value = int(env_raw)
            if value > 0:
                return value
        except ValueError:
            pass

    per_step = 60
    try:
        metadata = load_metadata(task_path).data
        environment = metadata.get("environment")
        if isinstance(environment, dict):
            raw = environment.get("timeout_seconds")
            if isinstance(raw, int) and raw > 0:
                per_step = raw
    except (OSError, ValueError):
        pass
    return max(300, per_step * 8)


def _select_eval_image(task_path: Path, image: str) -> str:
    if image != DEFAULT_EVAL_IMAGE:
        return image
    try:
        metadata = load_metadata(task_path).data
    except (OSError, ValueError):
        return image
    return DEFAULT_GO_EVAL_IMAGE if metadata.get("language") == "go" else image


def _env_default(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _forwarded_eval_env_keys() -> list[str]:
    keys = [
        "FEATURELIFTBENCH_COMMAND_OUTPUT_LIMIT_BYTES",
        "COMMAND_OUTPUT_LIMIT_BYTES",
        "EVAL_MEMORY_MB",
        "FEATURELIFTBENCH_EVAL_MEMORY_MB",
    ]
    return [key for key in keys if os.environ.get(key, "").strip()]


def _sandbox_payload(
    *,
    image: str,
    command: list[str],
    returncode: int,
    docker_sandbox_error: bool,
) -> dict[str, Any]:
    return {
        "backend": "docker",
        "image": image,
        "docker_returncode": returncode,
        "docker_sandbox_error": docker_sandbox_error,
        "network": "none",
        "memory": _env_default("FEATURELIFTBENCH_DOCKER_MEMORY", DEFAULT_DOCKER_MEMORY),
        "cpus": _env_default("FEATURELIFTBENCH_DOCKER_CPUS", DEFAULT_DOCKER_CPUS),
        "pids_limit": _env_default("FEATURELIFTBENCH_DOCKER_PIDS", DEFAULT_DOCKER_PIDS),
        "read_only": True,
        "cap_drop": "ALL",
        "no_new_privileges": True,
        "tmpfs": _env_default("FEATURELIFTBENCH_DOCKER_TMPFS", DEFAULT_DOCKER_TMPFS),
        "command": command,
    }


def _write_docker_failure_result(
    *,
    task_path: Path,
    submission_path: Path,
    output_path: Path,
    image: str,
    command: list[str],
    completed: _DockerEvalProcessResult,
    message: str,
    timed_out: bool = False,
) -> dict[str, Any]:
    logs_path = output_path / "logs"
    logs_path.mkdir(parents=True, exist_ok=True)
    (logs_path / "docker.stdout").write_text(completed.stdout or "", encoding="utf-8")
    (logs_path / "docker.stderr").write_text(completed.stderr or "", encoding="utf-8")
    resource_limited = _docker_resource_limited(completed)
    result: dict[str, Any] = {
        "task_id": task_path.name,
        "submission": submission_path.name,
        "status": "failed",
        "build_pass": False,
        "public_tests_pass": False,
        "hidden_tests_pass": False,
        "isolation_pass": False,
        "isolation": {
            "pass": False,
            "forbidden_imports_pass": False,
            "forbidden_dependencies_pass": False,
            "forbidden_runtime_capabilities_pass": False,
            "runtime_import_origin_pass": False,
            "source_filesystem_absent": False,
            "network_disabled": False,
            "submission_location_pass": False,
            "mount_allowlist_pass": False,
            "verification_mode": "docker_failure",
        },
        "test_pass": False,
        "original_import_pass": False,
        "evaluation_capsule_digest": "",
        "compactness_status": "not_run",
        "compactness": {
            "status": "not_run",
            "reason": "functional Docker evaluation failed before private metrics stage",
        },
        "environment": {
            "venv_dir": "",
            "python": "",
            "install_mode": "not-run",
        },
        "dependency_install": _empty_command_payload(),
        "eval_tooling": _empty_command_payload(),
        "submission_install": _empty_command_payload(),
        "build": _empty_command_payload(),
        "public_tests": _empty_command_payload(),
        "hidden_tests": _empty_command_payload(),
        "metrics": {},
        "scores": {
            "functional_gate": 0.0,
            "extraction_ratio": 1.0,
            "final_score": 0.0,
        },
        "logs": {
            "dir": str(logs_path),
        },
        "sandbox": _sandbox_payload(
            image=image,
            command=command,
            returncode=completed.returncode,
            docker_sandbox_error=True,
        ),
        "docker_returncode": completed.returncode,
        "docker_sandbox_error": True,
        "resource_limited": resource_limited,
        "timed_out": timed_out,
        "errors": [message],
    }
    if resource_limited:
        result["errors"].append("docker eval exceeded container resource limits")
    result_path = output_path / "result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _empty_command_payload() -> dict[str, Any]:
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


def _docker_resource_limited(completed: _DockerEvalProcessResult) -> bool:
    if completed.returncode in {137, -9}:
        return True
    text = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
    return "out of memory" in text or "oom" in text or "killed" in text
