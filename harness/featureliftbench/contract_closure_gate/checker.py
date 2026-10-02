"""Public-contract-only structural and behavior-evidence checker."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ..task_spec import canonical_json
from ..test_first_lift.cases import canonical_json as observation_json
from ..test_first_lift.cases import normalize_observation
from .common import CASES_DIR
from .common import CHECKER_VERSION
from .common import CHECK_SCHEMA
from .common import DEFAULT_CASE_TIMEOUT_SECONDS
from .common import DEFAULT_LITE_RESCUE_PLUS_BEHAVIOR_BUDGET_SECONDS
from .common import DEFAULT_LITE_RESCUE_PLUS_MAX_CASES
from .common import DEFAULT_V3_MAX_CASES
from .common import PUBLIC_CONTRACT_FILE
from .common import PUBLIC_WITNESS_FILE


_CASE_RUNNER = r"""
import importlib.util
import json
import sys
import traceback
from pathlib import Path

case_path = Path(sys.argv[1]).resolve()
function_name = sys.argv[2]
submission_root = Path(sys.argv[3]).resolve() if sys.argv[3] else None
executed_submission = False

def profile(frame, event, arg):
    global executed_submission
    if event == "call" and submission_root is not None:
        try:
            Path(frame.f_code.co_filename).resolve().relative_to(submission_root)
        except (ValueError, OSError):
            pass
        else:
            executed_submission = True
    return profile

sys.setprofile(profile)
try:
    spec = importlib.util.spec_from_file_location("flb_contract_case", case_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load case module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = getattr(module, function_name)()
    payload = {
        "ok": True,
        "raw": raw,
        "executed_submission": executed_submission,
    }
except BaseException as exc:
    payload = {
        "ok": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "error_module": getattr(exc, "name", None),
        "traceback_tail": traceback.format_exc()[-1500:],
        "executed_submission": executed_submission,
    }
finally:
    sys.setprofile(None)
print(json.dumps(payload, sort_keys=True, default=str))
"""


def _flatten_api(entries: Any) -> list[dict[str, Any]]:
    flattened: dict[str, dict[str, Any]] = {}

    def walk(items: Any) -> None:
        if not isinstance(items, list):
            return
        for raw in items:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("path") or "").strip()
            if path:
                existing = flattened.get(path, {})
                flattened[path] = {**existing, **raw, "path": path}
            walk(raw.get("members"))

    walk(entries)
    return [flattened[path] for path in sorted(flattened)]


def _check(
    check_id: str,
    *,
    category: str,
    status: str,
    severity: str,
    message: str,
    target: str = "",
    evidence: Any = None,
) -> dict[str, Any]:
    payload = {
        "id": check_id,
        "category": category,
        "status": status,
        "severity": severity,
        "message": message,
    }
    if target:
        payload["target"] = target
    if evidence is not None:
        payload["evidence"] = evidence
    return payload


def _load_contract(workspace: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = workspace / PUBLIC_CONTRACT_FILE
    if not path.is_file():
        raise ValueError(f"missing {PUBLIC_CONTRACT_FILE}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(
        payload.get("public_spec"), dict
    ):
        raise ValueError(f"invalid {PUBLIC_CONTRACT_FILE}")
    claimed = str(payload.get("contract_hash") or "")
    unhashed = {key: value for key, value in payload.items() if key != "contract_hash"}
    actual = hashlib.sha256(canonical_json(unhashed).encode("utf-8")).hexdigest()
    checks = [
        _check(
            "contract.provenance",
            category="provenance",
            status="pass" if claimed == actual else "fail",
            severity="hard",
            message=(
                "public contract hash matches generated payload"
                if claimed == actual
                else "PUBLIC_CONTRACT.json was modified after generation"
            ),
            target=PUBLIC_CONTRACT_FILE,
            evidence={"claimed": claimed, "actual": actual},
        )
    ]
    return payload, checks


def _compile_checks(submission: Path) -> list[dict[str, Any]]:
    if not submission.is_dir():
        return [
            _check(
                "submission.exists",
                category="structure",
                status="fail",
                severity="hard",
                message="submission directory is missing",
                target="submission/",
            )
        ]
    files = sorted(submission.rglob("*.py"))
    if not files:
        return [
            _check(
                "submission.python_files",
                category="structure",
                status="fail",
                severity="hard",
                message="submission contains no Python files",
                target="submission/",
            )
        ]
    errors = []
    for path in files:
        try:
            compile(path.read_bytes(), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            errors.append(
                f"{path.relative_to(submission)}: {type(exc).__name__}: {exc}"
            )
    return [
        _check(
            "submission.compile",
            category="structure",
            status="fail" if errors else "pass",
            severity="hard",
            message=(
                "; ".join(errors[:8])
                if errors
                else f"compiled {len(files)} Python files"
            ),
            target="submission/",
            evidence={"file_count": len(files), "errors": errors},
        )
    ]


def _forbidden_checks(
    submission: Path,
    forbidden: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked_imports = {
        str(value).strip()
        for value in forbidden.get("imports", [])
        if str(value).strip()
    }
    blocked_paths = {
        str(value).strip() for value in forbidden.get("paths", []) if str(value).strip()
    }
    import_hits: list[str] = []
    path_hits: list[str] = []
    if submission.is_dir():
        for path in sorted(submission.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(submission).as_posix()
            for blocked in blocked_paths:
                normalized = blocked.lstrip("./")
                if rel == normalized.rstrip("/") or rel.startswith(normalized):
                    path_hits.append(f"{rel} matches {blocked}")
            if path.suffix != ".py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if any(
                        name == item or name.startswith(f"{item}.")
                        for item in blocked_imports
                    ):
                        import_hits.append(
                            f"{rel}:{getattr(node, 'lineno', 0)} imports {name}"
                        )
                if isinstance(node, ast.Call) and node.args:
                    dynamic_import = (
                        isinstance(node.func, ast.Name) and node.func.id == "__import__"
                    ) or (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "import_module"
                    )
                    first_arg = node.args[0]
                    if (
                        dynamic_import
                        and isinstance(first_arg, ast.Constant)
                        and isinstance(first_arg.value, str)
                    ):
                        value = first_arg.value
                        if any(
                            value == item or value.startswith(f"{item}.")
                            for item in blocked_imports
                        ):
                            import_hits.append(
                                f"{rel}:{getattr(node, 'lineno', 0)} dynamically imports {value!r}"
                            )
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value
                    if any(item in value for item in blocked_paths):
                        path_hits.append(
                            f"{rel}:{getattr(node, 'lineno', 0)} references forbidden path"
                        )
    return [
        _check(
            "forbidden.imports",
            category="dependency",
            status="fail" if import_hits else "pass",
            severity="hard",
            message=(
                "; ".join(import_hits[:8])
                if import_hits
                else "no forbidden imports found"
            ),
            target="submission/",
            evidence={"blocked": sorted(blocked_imports), "hits": import_hits},
        ),
        _check(
            "forbidden.paths",
            category="dependency",
            status="fail" if path_hits else "pass",
            severity="hard",
            message=(
                "; ".join(path_hits[:8]) if path_hits else "no forbidden paths found"
            ),
            target="submission/",
            evidence={"blocked": sorted(blocked_paths), "hits": path_hits},
        ),
    ]


def _run_api_probe(
    workspace: Path,
    entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    harness_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="flb-contract-probe-") as temporary:
        temp = Path(temporary)
        entries_path = temp / "entries.json"
        entries_path.write_text(json.dumps(entries), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(harness_root), str(workspace / "submission")]
        )
        env["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "featureliftbench.contract_closure_gate.probe",
                "--submission",
                str(workspace / "submission"),
                "--entries",
                str(entries_path),
            ],
            cwd=temporary,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "probe failed").strip()[-2000:]
        return [], error
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return [], f"invalid API probe output: {exc}"
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return [], "API probe returned no results"
    return results, None


def _split_parameters(signature: str) -> tuple[list[str], bool]:
    text = signature.strip()
    if not text.startswith("("):
        raise ValueError("signature must start with '('")
    quote = ""
    escaped = False
    depth = 0
    closing = -1
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing < 0:
        raise ValueError("signature has no closing ')'")
    body = text[1:closing]
    parts: list[str] = []
    current: list[str] = []
    brackets: list[str] = []
    quote = ""
    escaped = False
    angle_depth = 0
    for char in body:
        if quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char in "([{":
            brackets.append(char)
        elif char in ")]}" and brackets:
            brackets.pop()
        elif char == "<" and "=" in "".join(current):
            angle_depth += 1
        elif char == ">" and angle_depth:
            angle_depth -= 1
        if char == "," and not brackets and not angle_depth:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current or body.endswith(","):
        parts.append("".join(current).strip())
    wildcard = any(part == "..." for part in parts)
    return [part for part in parts if part and part != "..."], wildcard


def _top_level_split(text: str, token: str) -> tuple[str, str | None]:
    brackets: list[str] = []
    quote = ""
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "([{":
            brackets.append(char)
        elif char in ")]}" and brackets:
            brackets.pop()
        elif char == token and not brackets:
            return text[:index], text[index + 1 :]
    return text, None


def parse_public_signature(signature: str) -> dict[str, Any]:
    """Parse inspect-style signatures without evaluating annotations/defaults."""

    parts, wildcard = _split_parameters(signature)
    positional_only_marker = parts.index("/") if "/" in parts else -1
    keyword_only = False
    parameters: list[dict[str, Any]] = []
    value_index = 0
    for part in parts:
        if part == "/":
            continue
        if part == "*":
            keyword_only = True
            continue
        default_left, default = _top_level_split(part, "=")
        name_left, _annotation = _top_level_split(default_left, ":")
        raw_name = name_left.strip()
        if raw_name.startswith("**"):
            name = raw_name[2:].strip()
            kind = "VAR_KEYWORD"
        elif raw_name.startswith("*"):
            name = raw_name[1:].strip()
            kind = "VAR_POSITIONAL"
            keyword_only = True
        else:
            name = raw_name
            if keyword_only:
                kind = "KEYWORD_ONLY"
            elif positional_only_marker >= 0 and value_index < positional_only_marker:
                kind = "POSITIONAL_ONLY"
            else:
                kind = "POSITIONAL_OR_KEYWORD"
        if not name.isidentifier():
            raise ValueError(f"invalid parameter {raw_name!r}")
        parameters.append(
            {
                "name": name,
                "kind": kind,
                "has_default": default is not None,
                "default_text": None if default is None else default.strip(),
            }
        )
        value_index += 1
    return {"parameters": parameters, "wildcard": wildcard}


def _literal(text: str | None) -> tuple[bool, Any]:
    if text is None or text == "..." or (text.startswith("<") and text.endswith(">")):
        return False, None
    try:
        return True, ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return False, None


def compare_signature(
    expected_text: str,
    actual: dict[str, Any],
    *,
    implicit_receiver: bool = False,
) -> tuple[str, str]:
    if not actual.get("available"):
        return "unknown", f"signature unavailable: {actual.get('error', '')}"
    try:
        expected = parse_public_signature(expected_text)
    except ValueError as exc:
        return "unknown", f"published signature could not be normalized: {exc}"
    actual_parameters = actual.get("parameters")
    if not isinstance(actual_parameters, list):
        return "unknown", "probe returned no signature parameters"
    expected_parameters = expected["parameters"]
    if (
        implicit_receiver
        and actual_parameters
        and actual_parameters[0].get("name") in {"self", "cls"}
        and (
            not expected_parameters
            or expected_parameters[0]["name"] != actual_parameters[0].get("name")
        )
    ):
        actual_parameters = actual_parameters[1:]
    if len(actual_parameters) < len(expected_parameters):
        return "fail", "actual signature omits explicitly published parameters"
    actual_by_name = {str(item.get("name")): item for item in actual_parameters}
    actual_positions = {
        str(item.get("name")): index for index, item in enumerate(actual_parameters)
    }
    explicit_positions = [
        actual_positions.get(item["name"], -1) for item in expected_parameters
    ]
    if explicit_positions != sorted(explicit_positions) or -1 in explicit_positions:
        return "fail", "explicitly published parameters are missing or reordered"
    pairs = [(item, actual_by_name.get(item["name"])) for item in expected_parameters]
    for expected_item, actual_item in pairs:
        if not isinstance(actual_item, dict):
            return "fail", f"missing parameter {expected_item['name']}"
        if expected_item["name"] != actual_item.get("name"):
            return (
                "fail",
                f"expected parameter {expected_item['name']}, got {actual_item.get('name')}",
            )
        if expected_item["kind"] != actual_item.get("kind"):
            return (
                "fail",
                f"{expected_item['name']}: expected {expected_item['kind']}, "
                f"got {actual_item.get('kind')}",
            )
        if expected_item["has_default"] != bool(actual_item.get("has_default")):
            return (
                "fail",
                f"{expected_item['name']}: required/default status differs",
            )
        expected_literal, expected_value = _literal(expected_item.get("default_text"))
        actual_literal, actual_value = _literal(actual_item.get("default_repr"))
        if expected_literal and actual_literal and expected_value != actual_value:
            return (
                "fail",
                f"{expected_item['name']}: expected default {expected_value!r}, "
                f"got {actual_value!r}",
            )
    if not expected["wildcard"] and len(actual_parameters) != len(expected_parameters):
        expected_names = {item["name"] for item in expected_parameters}
        extras = [
            str(item.get("name"))
            for item in actual_parameters
            if item.get("name") not in expected_names
        ]
        return (
            "fail",
            "actual signature adds unpublished parameters: "
            + ", ".join(extras),
        )
    return "pass", f"signature matches {expected_text}"


def _api_checks(workspace: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results, error = _run_api_probe(workspace, entries)
    if error:
        return [
            _check(
                "api.probe",
                category="api",
                status="fail",
                severity="hard",
                message=error,
                target="featurelifted",
            )
        ]
    by_path = {
        str(item.get("path")): item for item in results if isinstance(item, dict)
    }
    checks: list[dict[str, Any]] = []
    for entry in entries:
        path = str(entry.get("path"))
        result = by_path.get(path)
        if result is None:
            checks.append(
                _check(
                    f"api.{path}",
                    category="api",
                    status="fail",
                    severity="hard",
                    message="API probe produced no result",
                    target=path,
                )
            )
            continue
        status = str(result.get("status") or "fail")
        message = str(result.get("error") or f"resolved as {result.get('actual_type')}")
        checks.append(
            _check(
                f"api.{path}",
                category="api",
                status=status,
                severity="hard",
                message=message,
                target=path,
                evidence=result,
            )
        )
        signature_text = entry.get("signature")
        if (
            status == "pass"
            and isinstance(signature_text, str)
            and signature_text.strip()
        ):
            signature_status, signature_message = compare_signature(
                signature_text,
                result.get("signature") or {},
                implicit_receiver=str(entry.get("kind") or "").strip().lower()
                in {"method", "classmethod"},
            )
            checks.append(
                _check(
                    f"signature.{path}",
                    category="signature",
                    status=signature_status,
                    severity="hard",
                    message=signature_message,
                    target=path,
                    evidence={
                        "expected": signature_text,
                        "actual": (result.get("signature") or {}).get("text"),
                    },
                )
            )
    return checks


def _case_files(workspace: Path) -> list[Path]:
    root = workspace / CASES_DIR
    if not root.is_dir():
        return []
    return [
        path
        for path in sorted(root.rglob("*.py"))
        if path.is_file() and not path.name.startswith("_")
    ]


def _literal_assignment(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Name) and target.id == name for target in targets
            ):
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    return None
    return None


def _inspect_case(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return None, f"{path.name}: {type(exc).__name__}: {exc}"
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    meta = {
        "path": path,
        "case_id": _literal_assignment(tree, "CASE_ID"),
        "behavior_ids": _literal_assignment(tree, "BEHAVIOR_IDS"),
        "required_api": _literal_assignment(tree, "REQUIRED_API"),
        "mode": _literal_assignment(tree, "MODE"),
        "evidence": _literal_assignment(tree, "EVIDENCE"),
        "functions": functions,
    }
    case_id = meta["case_id"]
    if not isinstance(case_id, str) or not case_id.strip():
        return None, f"{path.name}: CASE_ID must be a non-empty literal string"
    for key in ("behavior_ids", "required_api", "evidence"):
        value = meta[key]
        if (
            not isinstance(value, (list, tuple))
            or not value
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            return None, f"{path.name}: {key.upper()} must be a non-empty string list"
        meta[key] = [str(item).strip() for item in value]
    mode = str(meta["mode"] or "").strip().lower()
    if mode not in {"differential", "direct"}:
        return None, f"{path.name}: MODE must be 'differential' or 'direct'"
    meta["mode"] = mode
    required_functions = (
        {"run_upstream", "run_featurelifted"}
        if mode == "differential"
        else {"check_featurelifted"}
    )
    missing = sorted(required_functions - functions)
    if missing:
        return None, f"{path.name}: missing {', '.join(missing)}"
    trivial: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assert)
            and isinstance(node.test, ast.Constant)
            and node.test.value is True
        ):
            trivial.append(f"assert True at line {node.lineno}")
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in {"skip", "skipif"}:
                trivial.append(f"unconditional {name} call at line {node.lineno}")
    if trivial:
        return None, f"{path.name}: " + "; ".join(trivial)
    return meta, None


def _case_env(workspace: Path, target_root: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    paths: list[str] = []
    if target_root is not None:
        paths.append(str(target_root))
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _run_case(
    workspace: Path,
    case_path: Path,
    function_name: str,
    *,
    target_root: Path | None,
    submission_root: Path | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        "w", suffix="_contract_case.py", delete=False
    ) as handle:
        handle.write(_CASE_RUNNER)
        runner = Path(handle.name)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                str(case_path),
                function_name,
                str(submission_root or ""),
            ],
            cwd=str(workspace),
            env=_case_env(workspace, target_root),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error_type": "Timeout", "error": "case timed out"}
    finally:
        runner.unlink(missing_ok=True)
    if completed.returncode != 0:
        return {
            "ok": False,
            "error_type": "RunnerError",
            "error": (completed.stderr or completed.stdout or "runner failed")[-1500:],
        }
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {"ok": False, "error_type": "ProtocolError", "error": str(exc)}
    return (
        result if isinstance(result, dict) else {"ok": False, "error": "invalid result"}
    )


def _normalized_run(
    result: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, str, str]:
    if not result.get("ok"):
        return (
            False,
            None,
            f"{result.get('error_type')}: {result.get('error')}",
            "execution_error",
        )
    raw = result.get("raw")
    required_keys = {"result", "exception", "state_after"}
    if not isinstance(raw, dict):
        return (
            False,
            None,
            "differential observation must be a dict with exactly result, "
            "exception, and state_after",
            "case_protocol_invalid",
        )
    actual_keys = set(raw)
    if actual_keys != required_keys:
        missing = sorted(required_keys - actual_keys)
        extra = sorted(actual_keys - required_keys)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        return (
            False,
            None,
            "differential observation must contain exactly result, exception, and "
            "state_after (" + "; ".join(details) + ")",
            "case_protocol_invalid",
        )
    try:
        return True, normalize_observation(raw), "", ""
    except ValueError as exc:
        return False, None, str(exc), "case_protocol_invalid"


def _checker_dependency_unavailable(result: dict[str, Any]) -> bool:
    """Match probe.v5: external missing modules are checker-env unknowns."""

    if result.get("error_type") != "ModuleNotFoundError":
        return False
    missing = str(result.get("error_module") or "").strip()
    return bool(missing) and missing != "featurelifted" and not missing.startswith(
        "featurelifted."
    )


def _upstream_dependency_unavailable(observation: Any) -> bool:
    """Detect cases whose entire upstream oracle is an import-environment error."""

    exception_types: list[str] = []
    successful_leaf = False

    def walk(value: Any) -> None:
        nonlocal successful_leaf
        if isinstance(value, dict):
            if "exception" in value and "result" in value:
                exception = value.get("exception")
                result = value.get("result")
                if exception:
                    exception_types.append(str(exception))
                elif not isinstance(result, (dict, list, tuple)):
                    successful_leaf = True
            for nested in value.values():
                walk(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                walk(nested)

    walk(observation)
    return (
        bool(exception_types)
        and not successful_leaf
        and all(name in {"ImportError", "ModuleNotFoundError"} for name in exception_types)
    )


def _evaluate_case(
    workspace: Path,
    meta: dict[str, Any],
    *,
    timeout_seconds: int,
    deadline: float | None = None,
) -> tuple[str, str, dict[str, Any]]:
    def remaining_timeout() -> int:
        if deadline is None:
            return max(1, int(timeout_seconds))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return 0
        return max(1, min(int(timeout_seconds), int(remaining + 0.999)))

    def budget_exhausted() -> tuple[str, str, dict[str, Any]]:
        return (
            "unknown",
            "shared behavior execution budget exhausted",
            {"budget_exhausted": True},
        )

    path = meta["path"]
    submission = workspace / "submission"
    with tempfile.TemporaryDirectory(prefix="flb-empty-contract-") as temporary:
        stub = Path(temporary)
        package = stub / "featurelifted"
        package.mkdir()
        (package / "__init__.py").write_text(
            "# intentionally empty\n", encoding="utf-8"
        )
        if meta["mode"] == "differential":
            upstream_root_candidates = [workspace / "repo" / "src", workspace / "repo"]
            upstream_path = os.pathsep.join(
                str(candidate)
                for candidate in upstream_root_candidates
                if candidate.exists()
            )
            # A temporary synthetic root lets _case_env receive both repo roots.
            env = os.environ.copy()
            env["PYTHONPATH"] = upstream_path
            current_timeout = remaining_timeout()
            if current_timeout <= 0:
                return budget_exhausted()
            first = _run_case_with_env(
                workspace,
                path,
                "run_upstream",
                env=env,
                timeout_seconds=current_timeout,
            )
            current_timeout = remaining_timeout()
            if current_timeout <= 0:
                return budget_exhausted()
            second = _run_case_with_env(
                workspace,
                path,
                "run_upstream",
                env=env,
                timeout_seconds=current_timeout,
            )
            first_ok, expected, first_error, first_error_kind = _normalized_run(first)
            second_ok, expected_again, second_error, second_error_kind = (
                _normalized_run(second)
            )
            if not first_ok or not second_ok:
                if "case_protocol_invalid" in {first_error_kind, second_error_kind}:
                    return (
                        "fail",
                        "differential case protocol invalid: "
                        f"{first_error or second_error}",
                        {
                            "error_kind": "case_protocol_invalid",
                            "upstream_first": first,
                            "upstream_second": second,
                        },
                    )
                return (
                    "unknown",
                    f"upstream case unavailable: {first_error or second_error}",
                    {
                        "upstream_first": first,
                        "upstream_second": second,
                    },
                )
            if observation_json(expected) != observation_json(expected_again):
                return (
                    "unknown",
                    "upstream result is not stable across two processes",
                    {
                        "upstream_first": expected,
                        "upstream_second": expected_again,
                    },
                )
            if _upstream_dependency_unavailable(expected):
                return (
                    "unknown",
                    "upstream dependency environment is unavailable",
                    {
                        "upstream_first": expected,
                        "upstream_second": expected_again,
                    },
                )
            current_timeout = remaining_timeout()
            if current_timeout <= 0:
                return budget_exhausted()
            candidate = _run_case(
                workspace,
                path,
                "run_featurelifted",
                target_root=submission,
                submission_root=submission,
                timeout_seconds=current_timeout,
            )
            candidate_ok, actual, candidate_error, candidate_error_kind = (
                _normalized_run(candidate)
            )
            if not candidate_ok:
                if _checker_dependency_unavailable(candidate):
                    return (
                        "unknown",
                        "checker dependency unavailable while running featurelifted case",
                        {"candidate": candidate},
                    )
                if candidate_error_kind == "case_protocol_invalid":
                    return (
                        "fail",
                        f"differential case protocol invalid: {candidate_error}",
                        {
                            "error_kind": "case_protocol_invalid",
                            "candidate": candidate,
                        },
                    )
                return (
                    "fail",
                    f"featurelifted case failed: {candidate_error}",
                    {"candidate": candidate},
                )
            if not candidate.get("executed_submission"):
                return (
                    "fail",
                    "case did not execute code under submission/featurelifted",
                    {"candidate": candidate},
                )
            if observation_json(actual) != observation_json(expected):
                return (
                    "fail",
                    "featurelifted observation differs from stable upstream",
                    {
                        "expected": expected,
                        "actual": actual,
                    },
                )
            current_timeout = remaining_timeout()
            if current_timeout <= 0:
                return budget_exhausted()
            stub_result = _run_case(
                workspace,
                path,
                "run_featurelifted",
                target_root=stub,
                submission_root=stub,
                timeout_seconds=current_timeout,
            )
            stub_ok, stub_observation, _, _ = _normalized_run(stub_result)
            if stub_ok and observation_json(stub_observation) == observation_json(
                expected
            ):
                return (
                    "fail",
                    "case passes against an empty featurelifted package",
                    {"stub": stub_observation},
                )
            return (
                "pass",
                "stable upstream and featurelifted observations match",
                {
                    "expected": expected,
                    "actual": actual,
                },
            )

        current_timeout = remaining_timeout()
        if current_timeout <= 0:
            return budget_exhausted()
        candidate = _run_case(
            workspace,
            path,
            "check_featurelifted",
            target_root=submission,
            submission_root=submission,
            timeout_seconds=current_timeout,
        )
        if not candidate.get("ok"):
            if _checker_dependency_unavailable(candidate):
                return (
                    "unknown",
                    "checker dependency unavailable while running direct case",
                    {"candidate": candidate},
                )
            return (
                "fail",
                f"direct assertion failed: {candidate.get('error_type')}: {candidate.get('error')}",
                {"candidate": candidate},
            )
        if not candidate.get("executed_submission"):
            return (
                "fail",
                "direct case did not execute code under submission/featurelifted",
                {"candidate": candidate},
            )
        current_timeout = remaining_timeout()
        if current_timeout <= 0:
            return budget_exhausted()
        stub_result = _run_case(
            workspace,
            path,
            "check_featurelifted",
            target_root=stub,
            submission_root=stub,
            timeout_seconds=current_timeout,
        )
        if stub_result.get("ok"):
            return (
                "fail",
                "direct case passes against an empty featurelifted package",
                {"stub": stub_result},
            )
        return (
            "pass",
            "direct assertions pass and reject an empty package",
            {
                "candidate": {"executed_submission": True},
                "stub_error_type": stub_result.get("error_type"),
            },
        )


def _run_case_with_env(
    workspace: Path,
    case_path: Path,
    function_name: str,
    *,
    env: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        "w", suffix="_contract_case.py", delete=False
    ) as handle:
        handle.write(_CASE_RUNNER)
        runner = Path(handle.name)
    try:
        completed = subprocess.run(
            [sys.executable, str(runner), str(case_path), function_name, ""],
            cwd=str(workspace),
            env=env,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error_type": "Timeout", "error": "case timed out"}
    finally:
        runner.unlink(missing_ok=True)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode != 0 or not lines:
        return {
            "ok": False,
            "error_type": "RunnerError",
            "error": (completed.stderr or completed.stdout or "runner failed")[-1500:],
        }
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error_type": "ProtocolError", "error": str(exc)}


def _behavior_checks(
    workspace: Path,
    public_spec: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    timeout_seconds: int,
    max_cases: int | None = None,
    total_budget_seconds: int | None = None,
    witness_behavior_id: str = "",
) -> list[dict[str, Any]]:
    behaviors = (
        public_spec.get("behaviors")
        if isinstance(public_spec.get("behaviors"), list)
        else []
    )
    published_behaviors = {
        str(item.get("id")): str(item.get("text") or "")
        for item in behaviors
        if isinstance(item, dict) and item.get("id")
    }
    published_api = {str(entry.get("path")) for entry in entries}
    checks: list[dict[str, Any]] = []
    valid_cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    case_paths = _case_files(workspace)
    if max_cases is not None and len(case_paths) > max_cases:
        checks.append(
            _check(
                "behavior.case.limit",
                category="behavior_evidence",
                status="fail",
                severity="soft",
                message=(
                    f"{len(case_paths)} behavior cases exceed the bounded execution limit "
                    f"of {max_cases}; only the first {max_cases} are evaluated"
                ),
                target=CASES_DIR,
            )
        )
        case_paths = case_paths[:max_cases]
    for path in case_paths:
        meta, error = _inspect_case(path)
        if error or meta is None:
            checks.append(
                _check(
                    f"behavior.case.{path.stem}",
                    category="behavior",
                    status="fail",
                    severity="soft",
                    message=error or "invalid behavior case",
                    target=path.relative_to(workspace).as_posix(),
                )
            )
            continue
        case_id = str(meta["case_id"])
        if case_id in seen_case_ids:
            checks.append(
                _check(
                    f"behavior.case.{case_id}",
                    category="behavior",
                    status="fail",
                    severity="soft",
                    message=f"duplicate CASE_ID {case_id}",
                    target=path.relative_to(workspace).as_posix(),
                )
            )
            continue
        seen_case_ids.add(case_id)
        invalid_behaviors = sorted(set(meta["behavior_ids"]) - set(published_behaviors))
        invalid_api = sorted(set(meta["required_api"]) - published_api)
        invalid_evidence = [
            source
            for source in meta["evidence"]
            if not _valid_case_evidence(
                workspace, source, behavior_ids=set(meta["behavior_ids"])
            )
        ]
        if invalid_behaviors or invalid_api or invalid_evidence:
            details = []
            if invalid_behaviors:
                details.append("unknown behavior IDs: " + ", ".join(invalid_behaviors))
            if invalid_api:
                details.append("unpublished API paths: " + ", ".join(invalid_api))
            if invalid_evidence:
                details.append("invalid evidence: " + ", ".join(invalid_evidence))
            checks.append(
                _check(
                    f"behavior.case.{case_id}",
                    category="behavior",
                    status="fail",
                    severity="soft",
                    message="; ".join(details),
                    target=path.relative_to(workspace).as_posix(),
                )
            )
            continue
        valid_cases.append(meta)
    covered: set[str] = set()
    deadline = (
        time.monotonic() + max(1, int(total_budget_seconds))
        if total_budget_seconds is not None
        else None
    )
    for meta in valid_cases:
        covered.update(meta["behavior_ids"])
        status, message, evidence = _evaluate_case(
            workspace,
            meta,
            timeout_seconds=timeout_seconds,
            deadline=deadline,
        )
        category = (
            "behavior_evidence"
            if evidence.get("error_kind") == "case_protocol_invalid"
            else "behavior"
        )
        checks.append(
            _check(
                f"behavior.case.{meta['case_id']}",
                category=category,
                status=status,
                severity="soft",
                message=message,
                target=meta["path"].relative_to(workspace).as_posix(),
                evidence={
                    "behavior_ids": meta["behavior_ids"],
                    "required_api": meta["required_api"],
                    "mode": meta["mode"],
                    "public_witness": bool(
                        witness_behavior_id
                        and meta["mode"] == "direct"
                        and witness_behavior_id in meta["behavior_ids"]
                    ),
                    "sources": meta["evidence"],
                    "runtime": evidence,
                },
            )
        )
    for behavior_id, text in sorted(published_behaviors.items()):
        checks.append(
            _check(
                f"behavior.coverage.{behavior_id}",
                category="behavior_coverage",
                status="pass" if behavior_id in covered else "fail",
                severity="soft",
                message=(
                    "mapped to at least one valid behavior case"
                    if behavior_id in covered
                    else "no valid behavior case maps this public clause"
                ),
                target=behavior_id,
                evidence={"public_text": text},
            )
        )
    return checks


def _valid_case_evidence(
    workspace: Path,
    source: str,
    *,
    behavior_ids: set[str],
) -> bool:
    if source.startswith("public_spec:"):
        return source.split(":", 1)[1] in behavior_ids
    if not source.startswith("repo/"):
        return False
    raw_path, separator, raw_line = source.rpartition(":")
    path_text = raw_path if separator and raw_line.isdigit() else source
    candidate = (workspace / path_text).resolve()
    try:
        candidate.relative_to((workspace / "repo").resolve())
    except ValueError:
        return False
    if not candidate.is_file():
        return False
    if separator and raw_line.isdigit():
        try:
            line_count = len(
                candidate.read_text(encoding="utf-8", errors="replace").splitlines()
            )
        except OSError:
            return False
        return 1 <= int(raw_line) <= max(1, line_count)
    return True


def _actionable_behavior_failure(item: dict[str, Any]) -> bool:
    if item.get("category") != "behavior" or item.get("status") != "fail":
        return False
    message = str(item.get("message") or "")
    return message.startswith(
        (
            "featurelifted observation differs from stable upstream",
            "featurelifted case failed:",
            "direct assertion failed:",
        )
    )


def _repairable_behavior_evidence_failure(item: dict[str, Any]) -> bool:
    if item.get("status") != "fail":
        return False
    if item.get("id") in {"behavior.smoke.required", "behavior.witness.required"}:
        return True
    evidence = item.get("evidence")
    runtime = evidence.get("runtime") if isinstance(evidence, dict) else None
    return (
        item.get("category") == "behavior_evidence"
        and isinstance(runtime, dict)
        and runtime.get("error_kind") == "case_protocol_invalid"
    )


def _load_public_witness_behavior_id(workspace: Path) -> str:
    path = workspace / PUBLIC_WITNESS_FILE
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    claimed = str(payload.get("witness_hash") or "")
    unhashed = {key: value for key, value in payload.items() if key != "witness_hash"}
    actual = hashlib.sha256(canonical_json(unhashed).encode("utf-8")).hexdigest()
    if not claimed or claimed != actual or payload.get("mode") != "direct":
        return ""
    return str(payload.get("behavior_id") or "")


def check_workspace(
    workspace_dir: str | Path,
    *,
    case_timeout_seconds: int = DEFAULT_CASE_TIMEOUT_SECONDS,
    check_mode: str = "full",
) -> dict[str, Any]:
    if check_mode not in {"full", "structure", "behavior", "micro", "lite_plus"}:
        raise ValueError(f"unsupported contract check mode: {check_mode}")
    workspace = Path(workspace_dir).resolve()
    contract, checks = _load_contract(workspace)
    public_spec = contract["public_spec"]
    witness_behavior_id = (
        _load_public_witness_behavior_id(workspace)
        if check_mode == "lite_plus"
        else ""
    )
    entries = _flatten_api(public_spec.get("required_api"))
    if check_mode in {"full", "structure", "micro", "lite_plus"}:
        checks.extend(_compile_checks(workspace / "submission"))
        forbidden = public_spec.get("forbidden")
        checks.extend(
            _forbidden_checks(
                workspace / "submission",
                forbidden if isinstance(forbidden, dict) else {},
            )
        )
        checks.extend(_api_checks(workspace, entries))
    if check_mode in {"full", "behavior", "micro", "lite_plus"}:
        checks.extend(
            _behavior_checks(
                workspace,
                public_spec,
                entries,
                timeout_seconds=case_timeout_seconds,
                max_cases=(
                    DEFAULT_LITE_RESCUE_PLUS_MAX_CASES
                    if check_mode == "lite_plus"
                    else DEFAULT_V3_MAX_CASES
                    if check_mode == "micro"
                    else None
                ),
                total_budget_seconds=(
                    DEFAULT_LITE_RESCUE_PLUS_BEHAVIOR_BUDGET_SECONDS
                    if check_mode == "lite_plus"
                    else None
                ),
                witness_behavior_id=witness_behavior_id,
            )
        )

    executable_behavior_checks = [
        item
        for item in checks
        if item.get("category") == "behavior"
        and isinstance(item.get("evidence"), dict)
        and "runtime" in item["evidence"]
    ]
    public_witness_checks = [
        item
        for item in executable_behavior_checks
        if isinstance(item.get("evidence"), dict)
        and item["evidence"].get("public_witness") is True
    ]
    if check_mode == "lite_plus" and not public_witness_checks:
        checks.append(
            _check(
                "behavior.witness.required",
                category="behavior_evidence",
                status="fail",
                severity="soft",
                message=(
                    "no valid executable direct case was provided for the selected "
                    f"public witness {witness_behavior_id or '<missing>'}"
                ),
                target=CASES_DIR,
            )
        )

    hard_failures = [
        item
        for item in checks
        if item["severity"] == "hard" and item["status"] == "fail"
    ]
    soft_open = [
        item
        for item in checks
        if item["severity"] == "soft" and item["status"] in {"fail", "unknown"}
    ]
    unknown = [item for item in checks if item["status"] == "unknown"]
    checker_environment_unknown = [
        item
        for item in unknown
        if isinstance(item.get("evidence"), dict)
        and item["evidence"].get("error_kind")
        == "checker_dependency_unavailable"
    ]
    actionable_behavior_failures = [
        item for item in checks if _actionable_behavior_failure(item)
    ]
    actionable_public_witness_failures = [
        item
        for item in actionable_behavior_failures
        if isinstance(item.get("evidence"), dict)
        and item["evidence"].get("public_witness") is True
    ]
    repairable_behavior_evidence_failures = [
        item for item in checks if _repairable_behavior_evidence_failure(item)
    ]
    micro_behavior_passes = [
        item
        for item in checks
        if item.get("category") == "behavior"
        and item.get("status") == "pass"
        and isinstance(item.get("evidence"), dict)
        and "runtime" in item["evidence"]
    ]
    public_witness_passes = [
        item
        for item in micro_behavior_passes
        if isinstance(item.get("evidence"), dict)
        and item["evidence"].get("public_witness") is True
    ]
    hard_gate_ok = not hard_failures
    if check_mode == "lite_plus":
        behavior_gate_ok = bool(public_witness_passes) and not (
            actionable_public_witness_failures
        )
    elif check_mode == "micro":
        behavior_gate_ok = bool(micro_behavior_passes) and not (
            actionable_behavior_failures
        )
    else:
        behavior_gate_ok = not soft_open
    closure_ok = hard_gate_ok and (
        behavior_gate_ok
        if check_mode in {"full", "behavior", "micro", "lite_plus"}
        else True
    )
    summary = {
        status: sum(1 for item in checks if item["status"] == status)
        for status in ("pass", "fail", "unknown")
    }
    return {
        "schema_version": CHECK_SCHEMA,
        "checker_version": CHECKER_VERSION,
        "task_id": contract.get("task_id"),
        "spec_hash": contract.get("spec_hash"),
        "contract_hash": contract.get("contract_hash"),
        "check_mode": check_mode,
        "hard_gate_ok": hard_gate_ok,
        "behavior_gate_ok": behavior_gate_ok,
        "closure_ok": closure_ok,
        "repair_needed": bool(
            hard_failures
            or (
                actionable_public_witness_failures
                if check_mode == "lite_plus"
                else actionable_behavior_failures
                or repairable_behavior_evidence_failures
            )
        ),
        "summary": summary,
        "required_api_count": len(entries),
        "behavior_count": len(public_spec.get("behaviors") or []),
        "hard_failure_count": len(hard_failures),
        "soft_open_count": len(soft_open),
        "actionable_behavior_failure_count": len(actionable_behavior_failures),
        "actionable_public_witness_failure_count": len(
            actionable_public_witness_failures
        ),
        "repairable_behavior_evidence_failure_count": len(
            repairable_behavior_evidence_failures
        ),
        "micro_behavior_pass_count": len(micro_behavior_passes),
        "public_witness_behavior_id": witness_behavior_id,
        "public_witness_pass_count": len(public_witness_passes),
        "behavior_execution_budget_seconds": (
            DEFAULT_LITE_RESCUE_PLUS_BEHAVIOR_BUDGET_SECONDS
            if check_mode == "lite_plus"
            else None
        ),
        "unknown_count": len(unknown),
        "checker_environment_unknown_count": len(checker_environment_unknown),
        "checks": checks,
    }
