"""Observation-only differential probes for repair with two behavioral oracles.

The probe chooses inputs and public observations, but it must not encode an
expected result.  In paired mode the same probe is executed with
``FLB_DIFF_TARGET=upstream``, ``baseline``, and ``candidate``.  Upstream
execution supplies the target behavior while the immutable pre-repair
baseline supplies the conservation behavior.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path
from typing import Any

from .agent_docker import (
    CONTAINER_WORKSPACE,
    DEFAULT_AGENT_DOCKER_CPUS,
    DEFAULT_AGENT_DOCKER_MEMORY,
    DEFAULT_AGENT_DOCKER_NETWORK,
    DEFAULT_AGENT_DOCKER_PIDS,
    DEFAULT_AGENT_DOCKER_TMPFS,
    DEFAULT_AGENT_IMAGE,
    _env_default,
    _uid_gid,
)


AUDIT_DIR = ".dpr"
AUDIT_FILE = "audit.jsonl"
DEFAULT_TIMEOUT_SECONDS = 60
MAX_CAPTURE_CHARS = 64_000
BASELINE_DIR = "baseline_submission"

_BANNED_TEXT = (
    "public_tests",
    "hidden_tests",
    "evaluation-capsule",
    "evaluation_capsule",
    "reference_solution",
)
_BANNED_IMPORT_ROOTS = {"pytest", "unittest"}


class ProbeValidationError(ValueError):
    """Raised when a probe is not observation-only or references evaluator data."""


def validate_probe(probe_path: str | Path) -> dict[str, Any]:
    """Validate that a probe observes behavior without declaring an oracle."""

    path = Path(probe_path).resolve()
    if not path.is_file():
        raise ProbeValidationError(f"probe not found: {path}")
    source = path.read_text(encoding="utf-8")
    lowered = source.lower()
    for token in _BANNED_TEXT:
        if token in lowered:
            raise ProbeValidationError(
                f"probe references forbidden evaluator artifact: {token}"
            )
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ProbeValidationError(f"probe is not valid Python: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            raise ProbeValidationError(
                "observation-only probes must not contain assert statements"
            )
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".", 1)[0] for alias in node.names}
            blocked = sorted(roots & _BANNED_IMPORT_ROOTS)
            if blocked:
                raise ProbeValidationError(
                    "observation-only probes must not import test frameworks: "
                    + ", ".join(blocked)
                )
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in _BANNED_IMPORT_ROOTS:
                raise ProbeValidationError(
                    f"observation-only probes must not import test framework: {root}"
                )

    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return {
        "path": str(path),
        "sha256": digest,
        "bytes": len(source.encode("utf-8")),
        "assertions": 0,
        "forbidden_evaluator_references": False,
    }


def _parse_observation(stdout: str) -> Any:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _target_pythonpath(workspace: Path, target: str) -> str:
    if target == "upstream":
        candidates = (
            workspace / "repo" / "src",
            workspace / "repo",
            workspace / AUDIT_DIR / "upstream_site",
        )
    elif target == "candidate":
        candidates = (workspace / "submission",)
    elif target == "baseline":
        candidates = (workspace / AUDIT_DIR / BASELINE_DIR,)
    else:
        raise ValueError(f"unsupported differential target: {target}")
    return os.pathsep.join(str(path) for path in candidates if path.exists())


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _audit_records(workspace: Path) -> list[dict[str, Any]]:
    path = workspace / AUDIT_DIR / AUDIT_FILE
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _paired_observation(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "target" in value
        and "control" in value
        and isinstance(value["target"], dict)
        and len(value["target"]) == 1
        and isinstance(value["control"], dict)
        and len(value["control"]) == 1
    )


def upstream_runtime_dependencies(workspace_dir: str | Path) -> list[str]:
    """Read declared upstream runtime dependencies without installing the repo."""

    workspace = Path(workspace_dir).resolve()
    pyproject = workspace / "repo" / "pyproject.toml"
    if not pyproject.is_file():
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    project = data.get("project")
    if not isinstance(project, dict):
        return []
    dependencies = project.get("dependencies")
    if not isinstance(dependencies, list):
        return []
    return [
        value.strip()
        for value in dependencies
        if isinstance(value, str) and value.strip()
    ]


def prepare_upstream_runtime_docker(
    workspace_dir: str | Path,
    *,
    docker_image: str | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Install only declared upstream runtime dependencies into the workspace."""

    workspace = Path(workspace_dir).resolve()
    dependencies = upstream_runtime_dependencies(workspace)
    result: dict[str, Any] = {
        "backend": "docker",
        "dependencies": dependencies,
        "dependency_count": len(dependencies),
        "ok": True,
        "returncode": 0,
        "stdout_tail": "",
        "stderr_tail": "",
        "timed_out": False,
    }
    if not dependencies:
        result["status"] = "not_required"
        return result

    site = workspace / AUDIT_DIR / "upstream_site"
    site.mkdir(parents=True, exist_ok=True)
    image = (docker_image or "").strip() or DEFAULT_AGENT_IMAGE
    container = f"flb-dpr-deps-{uuid.uuid4().hex[:12]}"
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        container,
        "--network",
        _env_default(
            "FEATURELIFTBENCH_AGENT_DOCKER_NETWORK",
            DEFAULT_AGENT_DOCKER_NETWORK,
        ),
        "--memory",
        _env_default(
            "FEATURELIFTBENCH_AGENT_DOCKER_MEMORY",
            DEFAULT_AGENT_DOCKER_MEMORY,
        ),
        "--cpus",
        _env_default(
            "FEATURELIFTBENCH_AGENT_DOCKER_CPUS",
            DEFAULT_AGENT_DOCKER_CPUS,
        ),
        "--pids-limit",
        _env_default(
            "FEATURELIFTBENCH_AGENT_DOCKER_PIDS",
            DEFAULT_AGENT_DOCKER_PIDS,
        ),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        _env_default(
            "FEATURELIFTBENCH_AGENT_DOCKER_TMPFS",
            DEFAULT_AGENT_DOCKER_TMPFS,
        ),
        "--user",
        _uid_gid(),
        "-w",
        str(CONTAINER_WORKSPACE),
        "-v",
        f"{workspace}:{CONTAINER_WORKSPACE}:rw",
        image,
        "python",
        "-m",
        "pip",
        "install",
        "--quiet",
        "--disable-pip-version-check",
        "--target",
        f"{CONTAINER_WORKSPACE}/{AUDIT_DIR}/upstream_site",
        *dependencies,
    ]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1, int(timeout_seconds)),
        )
        result["returncode"] = int(proc.returncode or 0)
        result["stdout_tail"] = (proc.stdout or "")[-3000:]
        result["stderr_tail"] = (proc.stderr or "")[-3000:]
        result["ok"] = proc.returncode == 0
        result["status"] = "installed" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        result["returncode"] = 124
        result["timed_out"] = True
        result["ok"] = False
        result["status"] = "timed_out"
        result["stdout_tail"] = (
            exc.stdout if isinstance(exc.stdout, str) else ""
        )[-3000:]
        result["stderr_tail"] = f"timed out after {timeout_seconds}s"
    return result


def _run_target(
    workspace: Path,
    probe: Path,
    target: str,
    *,
    python_executable: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["FLB_DIFF_TARGET"] = target
    env["PYTHONPATH"] = _target_pythonpath(workspace, target)
    try:
        proc = subprocess.run(
            [python_executable, str(probe)],
            cwd=str(workspace),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1, int(timeout_seconds)),
        )
        stdout = (proc.stdout or "")[-MAX_CAPTURE_CHARS:]
        stderr = (proc.stderr or "")[-MAX_CAPTURE_CHARS:]
        return {
            "returncode": int(proc.returncode or 0),
            "timed_out": False,
            "stdout": stdout,
            "stderr": stderr,
            "observation": _parse_observation(stdout),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "returncode": 124,
            "timed_out": True,
            "stdout": stdout[-MAX_CAPTURE_CHARS:],
            "stderr": (stderr or f"timed out after {timeout_seconds}s")[
                -MAX_CAPTURE_CHARS:
            ],
            "observation": _parse_observation(stdout),
        }


def run_differential_probe(
    workspace_dir: str | Path,
    probe_path: str | Path,
    *,
    python_executable: str = sys.executable,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    write_audit: bool = True,
    include_baseline: bool | None = None,
    require_paired: bool | None = None,
    single_probe: bool | None = None,
    max_calls: int | None = None,
) -> dict[str, Any]:
    """Run one frozen observation probe against behavioral oracle targets."""

    workspace = Path(workspace_dir).resolve()
    if include_baseline is None:
        include_baseline = _bool_env("FLB_DIFF_INCLUDE_BASELINE")
    if require_paired is None:
        require_paired = _bool_env("FLB_DIFF_REQUIRE_PAIRED")
    if single_probe is None:
        single_probe = _bool_env("FLB_DIFF_SINGLE_PROBE")
    if max_calls is None:
        max_calls = _int_env("FLB_DIFF_MAX_CALLS", 1_000_000)

    probe = Path(probe_path)
    if not probe.is_absolute():
        probe = workspace / probe
    probe = probe.resolve()
    try:
        probe.relative_to(workspace)
    except ValueError as exc:
        raise ProbeValidationError(
            f"probe must be located inside the workspace: {probe}"
        ) from exc

    validation = validate_probe(probe)
    relative_probe = str(probe.relative_to(workspace))
    prior_records = _audit_records(workspace)
    if len(prior_records) >= max_calls:
        raise ProbeValidationError(
            f"differential probe call budget exhausted ({max_calls})"
        )
    if single_probe:
        first_actionable = next(
            (
                record
                for record in prior_records
                if record.get("observations_comparable")
                and record.get("target_matches_upstream") is False
                and record.get("control_preserved_from_baseline") is True
            ),
            None,
        )
        if first_actionable is not None:
            frozen = first_actionable.get("probe") or {}
            if (
                frozen.get("path") != relative_probe
                or frozen.get("sha256") != validation["sha256"]
            ):
                raise ProbeValidationError(
                    "the first actionable probe is frozen; rerun the same "
                    "path and content after the repair"
                )

    if include_baseline and not (
        workspace / AUDIT_DIR / BASELINE_DIR
    ).is_dir():
        raise ProbeValidationError(
            f"paired mode requires {AUDIT_DIR}/{BASELINE_DIR}/"
        )

    upstream = _run_target(
        workspace,
        probe,
        "upstream",
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
    )
    baseline = (
        _run_target(
            workspace,
            probe,
            "baseline",
            python_executable=python_executable,
            timeout_seconds=timeout_seconds,
        )
        if include_baseline
        else None
    )
    candidate = _run_target(
        workspace,
        probe,
        "candidate",
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
    )
    observations_comparable = (
        upstream["returncode"] == 0
        and candidate["returncode"] == 0
        and upstream["observation"] is not None
        and candidate["observation"] is not None
        and (
            not include_baseline
            or (
                baseline is not None
                and baseline["returncode"] == 0
                and baseline["observation"] is not None
            )
        )
    )
    if observations_comparable and require_paired:
        targets = [upstream, candidate]
        if baseline is not None:
            targets.append(baseline)
        if not all(_paired_observation(item["observation"]) for item in targets):
            raise ProbeValidationError(
                "paired probes must print top-level 'target' and 'control' "
                "objects containing exactly one named observation each"
            )

    target_matches_upstream: bool | None = None
    control_preserved_from_baseline: bool | None = None
    if observations_comparable and require_paired and baseline is not None:
        target_matches_upstream = (
            candidate["observation"]["target"]
            == upstream["observation"]["target"]
        )
        control_preserved_from_baseline = (
            candidate["observation"]["control"]
            == baseline["observation"]["control"]
        )

    payload = {
        "schema_version": (
            "featureliftbench.differential_probe.v2"
            if include_baseline
            else "featureliftbench.differential_probe.v1"
        ),
        "protocol": (
            "paired_upstream_target_baseline_control"
            if include_baseline
            else "observation_only_upstream_candidate_diff"
        ),
        "probe": {
            **validation,
            "path": relative_probe,
        },
        "upstream": upstream,
        "candidate": candidate,
        "observations_comparable": observations_comparable,
        "observations_equal": (
            upstream["observation"] == candidate["observation"]
            if observations_comparable
            else None
        ),
    }
    if baseline is not None:
        payload["baseline"] = baseline
        payload["target_matches_upstream"] = target_matches_upstream
        payload["control_preserved_from_baseline"] = (
            control_preserved_from_baseline
        )
    if write_audit:
        audit_dir = workspace / AUDIT_DIR
        audit_dir.mkdir(parents=True, exist_ok=True)
        with (audit_dir / AUDIT_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def load_probe_audit(workspace_dir: str | Path) -> dict[str, Any]:
    """Summarize recorded differential-probe calls after an agent run."""

    workspace = Path(workspace_dir).resolve()
    path = workspace / AUDIT_DIR / AUDIT_FILE
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    if path.is_file():
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: {exc}")
                continue
            if isinstance(value, dict):
                records.append(value)
            else:
                errors.append(f"line {line_number}: record is not an object")

    comparable = sum(bool(record.get("observations_comparable")) for record in records)
    unequal = sum(
        record.get("observations_equal") is False
        for record in records
        if record.get("observations_comparable")
    )
    paired_records = [
        record
        for record in records
        if record.get("protocol") == "paired_upstream_target_baseline_control"
        and record.get("observations_comparable")
    ]
    open_index = next(
        (
            index
            for index, record in enumerate(paired_records)
            if record.get("target_matches_upstream") is False
            and record.get("control_preserved_from_baseline") is True
        ),
        None,
    )
    frozen_probe = (
        (paired_records[open_index].get("probe") or {})
        if open_index is not None
        else {}
    )
    frozen_sha = frozen_probe.get("sha256")
    frozen_path = frozen_probe.get("path")
    post_open_records = (
        paired_records[open_index:] if open_index is not None else []
    )
    one_frozen_probe = open_index is None or all(
        (record.get("probe") or {}).get("sha256") == frozen_sha
        and (record.get("probe") or {}).get("path") == frozen_path
        for record in post_open_records
    )
    saw_open_target = open_index is not None
    saw_accepted_repair = False
    control_regressions = 0
    if open_index is not None:
        control_regressions = sum(
            record.get("control_preserved_from_baseline") is False
            for record in paired_records[open_index + 1 :]
        )
        saw_accepted_repair = any(
            record.get("target_matches_upstream") is True
            and record.get("control_preserved_from_baseline") is True
            for record in paired_records[open_index + 1 :]
        )
    return {
        "path": str(path),
        "exists": path.is_file(),
        "records": len(records),
        "comparable_records": comparable,
        "unequal_records": unequal,
        "errors": errors,
        "tool_used": bool(records),
        "paired_records": len(paired_records),
        "one_frozen_probe": one_frozen_probe,
        "frozen_probe_path": frozen_path,
        "frozen_probe_sha256": frozen_sha,
        "saw_open_target": saw_open_target,
        "control_regression_records": control_regressions,
        "repair_accepted": saw_accepted_repair and one_frozen_probe,
        "protocol_compliant": (
            bool(records)
            and not errors
            and (not paired_records or one_frozen_probe)
        ),
    }
