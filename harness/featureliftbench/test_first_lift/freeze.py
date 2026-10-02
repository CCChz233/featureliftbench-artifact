"""Freeze / verify for Test-First Lift."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .cases import CaseError
from .cases import canonical_json
from .cases import discover_case_files
from .cases import flatten_required_api_paths
from .cases import format_case_error
from .cases import inspect_case
from .cases import run_case_function
from .cases import run_upstream_twice
from .common import CHARACTERIZATION_DIR
from .common import FREEZE_AUDIT_FILE
from .common import LOCK_FILE
from .common import MAX_CASES
from .common import MIN_CASES
from .common import ORACLE_FILE

LOCK_SCHEMA_V2 = "featureliftbench.test_first_lift_lock.v2"


def _load_metadata(workspace: Path) -> dict[str, Any]:
    path = workspace / "metadata.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _hash_characterization_files(workspace: Path) -> dict[str, str]:
    root = workspace / CHARACTERIZATION_DIR
    files: dict[str, str] = {}
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            rel = path.relative_to(root).as_posix()
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _legacy_characterization_lock_digest(files: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps({"files": files}, sort_keys=True).encode("utf-8")
    ).hexdigest()


def compute_characterization_lock(workspace_dir: str | Path) -> dict[str, Any]:
    """Compute v2 lock over characterization/ files and oracle.json."""

    workspace = Path(workspace_dir).resolve()
    files = _hash_characterization_files(workspace)
    oracle_path = workspace / ORACLE_FILE
    oracle_sha256 = (
        hashlib.sha256(oracle_path.read_bytes()).hexdigest()
        if oracle_path.is_file()
        else None
    )
    payload = {
        "files": files,
        "oracle_sha256": oracle_sha256,
    }
    lock = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "schema_version": LOCK_SCHEMA_V2,
        "files": files,
        "file_count": len(files),
        "oracle_sha256": oracle_sha256,
        "lock": lock,
        "legacy_characterization_lock": _legacy_characterization_lock_digest(files),
    }


def verify_characterization_frozen(workspace_dir: str | Path) -> dict[str, Any]:
    """Verify freeze lock.

    Accepts v2 locks (characterization + oracle) and legacy characterization-only
    locks so in-flight smoke runs are not broken mid-suite.
    """

    workspace = Path(workspace_dir).resolve()
    lock_path = workspace / LOCK_FILE
    if not lock_path.is_file():
        return {"ok": False, "error": f"missing {LOCK_FILE}"}
    expected = lock_path.read_text(encoding="utf-8").strip()
    if not (workspace / ORACLE_FILE).is_file():
        return {"ok": False, "error": f"missing {ORACLE_FILE}"}

    current = compute_characterization_lock(workspace)
    if current.get("lock") == expected:
        return {
            "ok": True,
            "lock": expected,
            "file_count": current.get("file_count"),
            "lock_schema": "v2",
            "oracle_sha256": current.get("oracle_sha256"),
        }

    legacy = current.get("legacy_characterization_lock")
    if legacy == expected:
        return {
            "ok": True,
            "lock": expected,
            "file_count": current.get("file_count"),
            "lock_schema": "legacy",
            "oracle_sha256": current.get("oracle_sha256"),
            "warning": (
                "accepted legacy characterization-only lock; "
                "oracle.json is not covered by this lock digest"
            ),
        }

    return {
        "ok": False,
        "error": "characterization/oracle lock mismatch (files modified after freeze)",
        "expected_lock": expected,
        "actual_lock": current.get("lock"),
        "legacy_characterization_lock": legacy,
        "lock_schema": "mismatch",
    }


def _install_empty_stub(submission: Path) -> None:
    if submission.exists():
        shutil.rmtree(submission)
    pkg = submission / "featurelifted"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        '"""Empty stub for Test-First Lift freeze gate."""\n',
        encoding="utf-8",
    )


def _reset_empty_submission(workspace: Path) -> None:
    submission = workspace / "submission"
    if submission.exists():
        shutil.rmtree(submission)
    submission.mkdir(parents=True, exist_ok=True)


def _load_required_api_paths(workspace: Path) -> list[str]:
    char_req = workspace / CHARACTERIZATION_DIR / "REQUIRED_API.json"
    if char_req.is_file():
        try:
            payload = json.loads(char_req.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            required = payload.get("required_api")
            if isinstance(required, list):
                return sorted({str(x).strip() for x in required if str(x).strip()})
    return flatten_required_api_paths(_load_metadata(workspace))


def freeze_characterization(
    workspace_dir: str | Path,
    *,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    errors: list[str] = []
    case_files = discover_case_files(workspace)
    if len(case_files) < MIN_CASES:
        result = {
            "ok": False,
            "freeze_success": False,
            "errors": [f"need at least {MIN_CASES} characterization case(s)"],
            "valid_case_count": 0,
        }
        _write_freeze_audit(workspace, result)
        return result
    if len(case_files) > MAX_CASES:
        result = {
            "ok": False,
            "freeze_success": False,
            "errors": [f"too many cases ({len(case_files)}); max is {MAX_CASES}"],
            "valid_case_count": 0,
        }
        _write_freeze_audit(workspace, result)
        return result

    inspected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in case_files:
        try:
            meta = inspect_case(path)
        except CaseError as exc:
            errors.append(format_case_error(exc))
            continue
        if meta["case_id"] in seen_ids:
            errors.append(f"duplicate CASE_ID: {meta['case_id']}")
            continue
        seen_ids.add(meta["case_id"])
        inspected.append(meta)
    if errors:
        result = {
            "ok": False,
            "freeze_success": False,
            "errors": errors,
            "valid_case_count": 0,
        }
        _write_freeze_audit(workspace, result)
        return result

    observations: dict[str, Any] = {}
    for meta in inspected:
        try:
            obs = run_upstream_twice(
                workspace,
                meta["path"],
                timeout_seconds=timeout_seconds,
            )
        except CaseError as exc:
            errors.append(format_case_error(exc))
            continue
        observations[meta["case_id"]] = {
            "case_id": meta["case_id"],
            "task_clause": meta["task_clause"],
            "required_api": meta["required_api"],
            "source_file": meta["relpath"],
            "source_sha256": meta["sha256"],
            "observation": obs,
        }
    if errors:
        result = {
            "ok": False,
            "freeze_success": False,
            "errors": errors,
            "valid_case_count": 0,
            "case_ids": [m["case_id"] for m in inspected],
        }
        _write_freeze_audit(workspace, result)
        return result

    submission = workspace / "submission"
    backup = workspace / ".submission_tfl_backup"
    if backup.exists():
        shutil.rmtree(backup)
    if submission.exists():
        shutil.move(str(submission), str(backup))
    _install_empty_stub(submission)

    stub_failures = 0
    stub_details: list[dict[str, Any]] = []
    vacuous_cases: list[str] = []
    for meta in inspected:
        case_id = meta["case_id"]
        expected = observations[case_id]["observation"]
        try:
            actual = run_case_function(
                workspace,
                meta["path"],
                function_name="run_featurelifted",
                target="featurelifted",
                timeout_seconds=timeout_seconds,
            )
            if canonical_json(actual) == canonical_json(expected):
                stub_details.append({"case_id": case_id, "status": "vacuous_pass"})
                vacuous_cases.append(case_id)
            else:
                stub_failures += 1
                stub_details.append({"case_id": case_id, "status": "mismatch_ok"})
        except CaseError:
            stub_failures += 1
            stub_details.append({"case_id": case_id, "status": "raised_ok"})

    # Discard any pre-freeze submission; Phase B must start empty.
    shutil.rmtree(submission, ignore_errors=True)
    if backup.exists():
        shutil.rmtree(backup)

    if stub_failures != len(inspected) or vacuous_cases:
        result = {
            "ok": False,
            "freeze_success": False,
            "errors": [
                "every case must fail against an empty featurelifted stub; "
                "vacuous cases: "
                + (", ".join(vacuous_cases) if vacuous_cases else "(none reported)")
            ],
            "stub_details": stub_details,
            "vacuous_cases": vacuous_cases,
            "valid_case_count": len(inspected),
        }
        _write_freeze_audit(workspace, result)
        _reset_empty_submission(workspace)
        return result

    required_paths = _load_required_api_paths(workspace)
    declared: set[str] = set()
    for meta in inspected:
        declared.update(meta["required_api"])
    missing_required = sorted(set(required_paths) - declared) if required_paths else []
    if required_paths and missing_required:
        result = {
            "ok": False,
            "freeze_success": False,
            "errors": [
                "Required API not covered by any case REQUIRED_API: "
                + ", ".join(missing_required[:12])
                + (" ..." if len(missing_required) > 12 else "")
            ],
            "required_api_coverage": {
                "required_count": len(required_paths),
                "covered_count": len(required_paths) - len(missing_required),
                "missing": missing_required,
            },
            "valid_case_count": len(inspected),
            "stub_details": stub_details,
        }
        _write_freeze_audit(workspace, result)
        _reset_empty_submission(workspace)
        return result

    oracle_payload = {
        "schema_version": "featureliftbench.test_first_lift_oracle.v1",
        "cases": observations,
    }
    (workspace / ORACLE_FILE).write_text(
        json.dumps(oracle_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lock_meta = compute_characterization_lock(workspace)
    (workspace / LOCK_FILE).write_text(str(lock_meta["lock"]) + "\n", encoding="utf-8")
    _reset_empty_submission(workspace)

    result = {
        "ok": True,
        "freeze_success": True,
        "errors": [],
        "valid_case_count": len(inspected),
        "case_ids": [m["case_id"] for m in inspected],
        "lock": lock_meta["lock"],
        "lock_schema": "v2",
        "oracle_sha256": lock_meta.get("oracle_sha256"),
        "stub_details": stub_details,
        "vacuous_cases": [],
        "required_api_coverage": {
            "required_count": len(required_paths),
            "covered_count": len(required_paths) - len(missing_required),
            "missing": missing_required,
        },
        "oracle_file": ORACLE_FILE,
        "lock_file": LOCK_FILE,
        "submission_cleared": True,
    }
    _write_freeze_audit(workspace, result)
    return result


def verify_characterization(
    workspace_dir: str | Path,
    *,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    frozen = verify_characterization_frozen(workspace)
    if not frozen.get("ok"):
        return {
            "ok": False,
            "characterization_pass": False,
            "errors": [str(frozen.get("error") or "not frozen")],
            "frozen": frozen,
        }

    oracle = json.loads((workspace / ORACLE_FILE).read_text(encoding="utf-8"))
    cases = oracle.get("cases") if isinstance(oracle, dict) else None
    if not isinstance(cases, dict) or not cases:
        return {
            "ok": False,
            "characterization_pass": False,
            "errors": ["oracle.json has no cases"],
            "frozen": frozen,
        }

    by_id = {
        inspect_case(path)["case_id"]: path for path in discover_case_files(workspace)
    }
    errors: list[str] = []
    details: list[dict[str, Any]] = []
    passed = 0
    for case_id, entry in sorted(cases.items()):
        path = by_id.get(case_id)
        if path is None:
            errors.append(f"missing characterization file for case {case_id}")
            continue
        expected = entry.get("observation") if isinstance(entry, dict) else None
        try:
            actual = run_case_function(
                workspace,
                path,
                function_name="run_featurelifted",
                target="featurelifted",
                timeout_seconds=timeout_seconds,
            )
        except CaseError as exc:
            errors.append(format_case_error(exc))
            details.append({"case_id": case_id, "status": "error"})
            continue
        if canonical_json(actual) != canonical_json(expected):
            errors.append(f"{case_id}: observation mismatch vs oracle")
            details.append({"case_id": case_id, "status": "mismatch"})
            continue
        passed += 1
        details.append({"case_id": case_id, "status": "pass"})

    ok = not errors and passed == len(cases)
    return {
        "ok": ok,
        "characterization_pass": ok,
        "passed": passed,
        "total": len(cases),
        "errors": errors,
        "details": details,
        "frozen": frozen,
    }


def _write_freeze_audit(workspace: Path, result: dict[str, Any]) -> None:
    payload = {
        "schema_version": "featureliftbench.test_first_lift_freeze.v1",
        **result,
    }
    (workspace / FREEZE_AUDIT_FILE).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
