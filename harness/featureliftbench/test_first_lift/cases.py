"""Discover and execute characterization cases."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from .common import CHARACTERIZATION_DIR
from .common import DEFAULT_CASE_TIMEOUT_SECONDS


class CaseError(ValueError):
    """Raised when a characterization case is invalid or fails."""


def discover_case_files(workspace_dir: str | Path) -> list[Path]:
    root = Path(workspace_dir).resolve() / CHARACTERIZATION_DIR
    if not root.is_dir():
        return []
    files = [
        path
        for path in sorted(root.rglob("*.py"))
        if path.is_file()
        and not path.name.startswith("_")
        and path.name != "__init__.py"
    ]
    return files


def load_case_module(case_path: Path) -> Any:
    path = case_path.resolve()
    spec = importlib.util.spec_from_file_location(
        f"flb_tfl_case_{path.stem}_{hashlib.sha1(str(path).encode()).hexdigest()[:8]}",
        path,
    )
    if spec is None or spec.loader is None:
        raise CaseError(f"cannot load case module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_case(case_path: Path) -> dict[str, Any]:
    module = load_case_module(case_path)
    missing = [
        name
        for name in ("CASE_ID", "TASK_CLAUSE", "REQUIRED_API", "run_upstream", "run_featurelifted")
        if not hasattr(module, name)
    ]
    if missing:
        raise CaseError(f"{case_path.name}: missing {', '.join(missing)}")
    case_id = str(getattr(module, "CASE_ID")).strip()
    if not case_id:
        raise CaseError(f"{case_path.name}: empty CASE_ID")
    clause = str(getattr(module, "TASK_CLAUSE")).strip()
    if not clause:
        raise CaseError(f"{case_path.name}: empty TASK_CLAUSE")
    required = getattr(module, "REQUIRED_API")
    if not isinstance(required, (list, tuple)) or not required:
        raise CaseError(f"{case_path.name}: REQUIRED_API must be a non-empty list")
    required_paths = [str(item).strip() for item in required if str(item).strip()]
    if not required_paths:
        raise CaseError(f"{case_path.name}: REQUIRED_API has no usable paths")
    if not callable(getattr(module, "run_upstream")):
        raise CaseError(f"{case_path.name}: run_upstream must be callable")
    if not callable(getattr(module, "run_featurelifted")):
        raise CaseError(f"{case_path.name}: run_featurelifted must be callable")
    return {
        "path": case_path,
        "relpath": case_path.name,
        "case_id": case_id,
        "task_clause": clause,
        "required_api": required_paths,
        "sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
    }


def normalize_observation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CaseError(f"observation must be a dict, got {type(raw).__name__}")
    exception = raw.get("exception")
    if exception is None and "exception" not in raw:
        exception = None
    if isinstance(exception, BaseException):
        exception = {"type": type(exception).__name__}
    elif isinstance(exception, type) and issubclass(exception, BaseException):
        exception = {"type": exception.__name__}
    elif isinstance(exception, str):
        exception = {"type": exception.split(":")[0].strip() or exception}
    elif isinstance(exception, dict):
        exception = {"type": str(exception.get("type") or "Exception")}
    elif exception is not None:
        exception = {"type": type(exception).__name__}

    payload = {
        "result": raw.get("result"),
        "exception": exception,
        "state_after": raw.get("state_after"),
    }
    # Preserve optional stable extras the agent chose, excluding secrets/noise.
    for key, value in raw.items():
        if key in payload:
            continue
        if key in {"inputs", "pre_state", "return", "post_state"}:
            payload[key] = value
    try:
        json.dumps(payload, sort_keys=True, default=_json_default)
    except TypeError as exc:
        raise CaseError(f"observation is not JSON-serializable: {exc}") from exc
    return json.loads(json.dumps(payload, sort_keys=True, default=_json_default))


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _pythonpath_for_target(workspace: Path, target: str) -> str:
    parts: list[str] = []
    if target == "upstream":
        for candidate in (workspace / "repo" / "src", workspace / "repo"):
            if candidate.exists():
                parts.append(str(candidate))
    elif target == "featurelifted":
        parts.append(str(workspace / "submission"))
    else:
        raise ValueError(f"unknown target: {target}")
    # Keep stdlib imports working; prepend target paths.
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


_RUNNER_SOURCE = r'''
import importlib.util
import json
import sys
from pathlib import Path

case_path = Path(sys.argv[1]).resolve()
fn_name = sys.argv[2]
spec = importlib.util.spec_from_file_location("flb_tfl_case", case_path)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)
fn = getattr(module, fn_name)
raw = fn()
if not isinstance(raw, dict):
    raise SystemExit(f"observation must be dict, got {type(raw).__name__}")
exception = raw.get("exception")
if isinstance(exception, BaseException):
    raw = dict(raw)
    raw["exception"] = {"type": type(exception).__name__}
elif isinstance(exception, type):
    raw = dict(raw)
    raw["exception"] = {"type": exception.__name__}
print(json.dumps(raw, sort_keys=True, default=str))
'''


def run_case_function(
    workspace_dir: str | Path,
    case_path: Path,
    *,
    function_name: str,
    target: str,
    timeout_seconds: int = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    case_path = case_path.resolve()
    with tempfile.NamedTemporaryFile("w", suffix="_tfl_runner.py", delete=False) as handle:
        handle.write(_RUNNER_SOURCE)
        runner = Path(handle.name)
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath_for_target(workspace, target)
    env["FLB_TFL_TARGET"] = target
    try:
        completed = subprocess.run(
            [sys.executable, str(runner), str(case_path), function_name],
            cwd=str(workspace),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CaseError(
            f"{case_path.name}:{function_name} timed out after {timeout_seconds}s"
        ) from exc
    finally:
        runner.unlink(missing_ok=True)

    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise CaseError(
            f"{case_path.name}:{function_name} failed (rc={completed.returncode}): "
            f"{err[-1500:]}"
        )
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise CaseError(f"{case_path.name}:{function_name} produced no JSON observation")
    try:
        raw = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise CaseError(
            f"{case_path.name}:{function_name} stdout is not JSON: {lines[-1][:300]}"
        ) from exc
    return normalize_observation(raw)


def run_upstream_twice(
    workspace_dir: str | Path,
    case_path: Path,
    *,
    timeout_seconds: int = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    first = run_case_function(
        workspace_dir,
        case_path,
        function_name="run_upstream",
        target="upstream",
        timeout_seconds=timeout_seconds,
    )
    second = run_case_function(
        workspace_dir,
        case_path,
        function_name="run_upstream",
        target="upstream",
        timeout_seconds=timeout_seconds,
    )
    if canonical_json(first) != canonical_json(second):
        raise CaseError(
            f"{case_path.name}: upstream observation not stable across two processes"
        )
    return first


def flatten_required_api_paths(metadata: dict[str, Any] | None) -> list[str]:
    """Return Required API paths that characterization must mention.

    Prefer callables (method/function). Classes with no members are included
    so a bare required class cannot be silently dropped.
    """

    if not isinstance(metadata, dict):
        return []
    public_spec = metadata.get("public_spec")
    if not isinstance(public_spec, dict):
        return []
    required = public_spec.get("required_api")
    if not isinstance(required, list):
        return []
    paths: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            path = str(node.get("path") or "").strip()
            kind = str(node.get("kind") or "").strip().lower()
            members = node.get("members")
            member_list = members if isinstance(members, list) else []
            if kind in {"method", "function", "classmethod", "staticmethod"} and path:
                paths.append(path)
            elif path and not member_list and kind in {"class", "attribute", "property", ""}:
                paths.append(path)
            for member in member_list:
                _walk(member)
        elif isinstance(node, str) and node.strip():
            paths.append(node.strip())

    for item in required:
        _walk(item)
    return sorted(set(paths))


def format_case_error(exc: BaseException) -> str:
    return "".join(traceback.format_exception_only(type(exc), exc)).strip()
