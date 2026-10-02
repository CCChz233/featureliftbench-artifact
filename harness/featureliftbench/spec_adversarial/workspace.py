"""Workspace install + prompt appendix for Spec-grounded adversarial self-test."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from .common import CASES_DIR
from .common import CHECKER_NAME
from .common import MATRIX_FILE
from .matrix import build_contract_matrix
from .matrix import scenario_behavior_ids


_STUB_TEMPLATE = '''\
"""Scenario stub for {behavior_id}. Fill run_featurelifted; optionally run_upstream."""

BEHAVIOR_ID = "{behavior_id}"
REQUIRED_API = {required_api!r}
BEHAVIOR_TEXT = {behavior_text!r}

# Set True after you implement a real scenario (not a placeholder).
FILLED = False


def run_featurelifted():
    """Exercise submission/featurelifted for this behavior.

    Return a dict with:
      result: JSON-stable value (or None)
      exception_type: exception class name string, or None
    Compare exception types only — never messages.
    """
    raise NotImplementedError("fill run_featurelifted for {behavior_id}")


def run_upstream():
    """Optional. Same inputs via a symbol you discovered under repo/.

    Return the same shape as run_featurelifted, or leave as NotImplementedError
    if you are not dual-running this behavior.
    """
    raise NotImplementedError("optional upstream dual-run for {behavior_id}")
'''


_CHECKER_SOURCE = r'''#!/usr/bin/env python3
"""Check import surface + filled contract_cases scenarios. No Hidden / public_tests."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(path: str) -> Any:
    parts = path.split(".")
    if len(parts) < 2:
        raise ImportError(f"invalid API path: {path}")
    module_name = parts[0]
    attr_parts = parts[1:]
    module = importlib.import_module(module_name)
    value: Any = module
    for part in attr_parts:
        value = getattr(value, part)
    return value


def _normalize(obs: Any) -> dict[str, Any]:
    if not isinstance(obs, dict):
        raise TypeError(f"observation must be a dict, got {type(obs).__name__}")
    exception = obs.get("exception_type")
    if exception is None and "exception" in obs:
        raw = obs.get("exception")
        if isinstance(raw, BaseException):
            exception = type(raw).__name__
        elif isinstance(raw, type) and issubclass(raw, BaseException):
            exception = raw.__name__
        elif isinstance(raw, dict):
            exception = str(raw.get("type") or "") or None
        elif isinstance(raw, str):
            exception = raw.split(":")[0].strip() or None
        else:
            exception = None
    if isinstance(exception, type) and issubclass(exception, BaseException):
        exception = exception.__name__
    return {
        "result": obs.get("result"),
        "exception_type": exception,
    }


def _load_case(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"flb_sa_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _append_ledger(workspace: Path, payload: dict[str, Any]) -> None:
    ledger = workspace / "agent" / "contract_check.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def check_import_surface(workspace: Path, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    submission = workspace / "submission"
    if str(submission) not in sys.path:
        sys.path.insert(0, str(submission))
    rows: list[dict[str, Any]] = []
    for entry in matrix.get("required_api") or []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        ok = False
        error = ""
        try:
            _resolve_path(path)
            ok = True
        except Exception as exc:  # noqa: BLE001 — surface every import failure
            error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "row_kind": "required_api",
                "id": path,
                "ok": ok,
                "error": error,
            }
        )
    return rows


def check_scenarios(
    workspace: Path,
    matrix: dict[str, Any],
    *,
    oracle_import: str | None,
) -> list[dict[str, Any]]:
    cases_dir = workspace / "contract_cases"
    submission = workspace / "submission"
    if str(submission) not in sys.path:
        sys.path.insert(0, str(submission))
    if oracle_import:
        repo = workspace / "repo"
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        # Many upstream packages live as top-level modules under repo/.
        for child in repo.iterdir() if repo.is_dir() else []:
            if child.is_dir() and (child / "__init__.py").is_file():
                parent = str(child.parent)
                if parent not in sys.path:
                    sys.path.insert(0, parent)

    rows: list[dict[str, Any]] = []
    for behavior in matrix.get("behaviors") or []:
        if not isinstance(behavior, dict) or not behavior.get("needs_scenario"):
            continue
        behavior_id = str(behavior.get("id") or "")
        case_path = cases_dir / f"{behavior_id}.py"
        row: dict[str, Any] = {
            "row_kind": "behavior",
            "id": behavior_id,
            "ok": False,
            "filled": False,
            "error": "",
            "oracle_compared": False,
            "oracle_match": None,
        }
        if not case_path.is_file():
            row["error"] = f"missing stub {case_path.name}"
            rows.append(row)
            continue
        try:
            module = _load_case(case_path)
            filled = bool(getattr(module, "FILLED", False))
            row["filled"] = filled
            if not filled:
                row["error"] = "FILLED is False; implement a real scenario"
                rows.append(row)
                continue
            fl_obs = _normalize(module.run_featurelifted())
            row["featurelifted"] = fl_obs
            if fl_obs.get("exception_type") and "NotImplementedError" in str(
                fl_obs.get("exception_type")
            ):
                row["error"] = "run_featurelifted still raises NotImplementedError"
                rows.append(row)
                continue
            # A filled scenario that returns is treated as green for the row
            # unless dual-run disagrees.
            row["ok"] = True
            if oracle_import or hasattr(module, "run_upstream"):
                try:
                    up_raw = module.run_upstream()
                except NotImplementedError:
                    up_raw = None
                except Exception as exc:  # noqa: BLE001
                    row["oracle_compared"] = True
                    row["oracle_match"] = False
                    row["ok"] = False
                    row["error"] = f"upstream error: {type(exc).__name__}: {exc}"
                    rows.append(row)
                    continue
                if up_raw is not None:
                    up_obs = _normalize(up_raw)
                    row["upstream"] = up_obs
                    row["oracle_compared"] = True
                    match = (
                        up_obs.get("exception_type") == fl_obs.get("exception_type")
                        and up_obs.get("result") == fl_obs.get("result")
                    )
                    row["oracle_match"] = match
                    if not match:
                        row["ok"] = False
                        row["error"] = "featurelifted vs upstream mismatch"
        except NotImplementedError as exc:
            row["error"] = f"NotImplementedError: {exc}"
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["traceback"] = traceback.format_exc(limit=4)
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace root (default: cwd)",
    )
    parser.add_argument(
        "--oracle-import",
        default="",
        help="optional hint string recorded in the ledger; dual-run uses each case's run_upstream",
    )
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    matrix_path = workspace / "contract_matrix.json"
    if not matrix_path.is_file():
        print(f"missing {matrix_path}", file=sys.stderr)
        return 2
    matrix = _load_json(matrix_path)
    api_rows = check_import_surface(workspace, matrix)
    scenario_rows = check_scenarios(
        workspace,
        matrix,
        oracle_import=args.oracle_import.strip() or None,
    )
    all_rows = api_rows + scenario_rows
    ok = all(bool(row.get("ok")) for row in all_rows) and all(
        bool(row.get("filled", True))
        for row in scenario_rows
        if row.get("row_kind") == "behavior"
    )
    # Require every scenario row filled and ok; API rows must import.
    ok = all(bool(row.get("ok")) for row in api_rows)
    for row in scenario_rows:
        if not row.get("filled") or not row.get("ok"):
            ok = False
            break
    payload = {
        "ok": ok,
        "oracle_import": args.oracle_import.strip() or None,
        "api_rows": api_rows,
        "scenario_rows": scenario_rows,
        "red_count": sum(1 for row in all_rows if not row.get("ok")),
        "green_count": sum(1 for row in all_rows if row.get("ok")),
    }
    _append_ledger(workspace, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def install_spec_adversarial_workspace(
    workspace_dir: str | Path,
    *,
    public_spec: dict[str, Any],
) -> dict[str, Any]:
    """Install matrix, stubs, and checker. Never write source_entrypoints."""

    workspace = Path(workspace_dir).resolve()
    matrix = build_contract_matrix(public_spec)
    (workspace / MATRIX_FILE).write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cases_dir = workspace / CASES_DIR
    cases_dir.mkdir(parents=True, exist_ok=True)
    (cases_dir / "__init__.py").write_text("", encoding="utf-8")
    (cases_dir / "README.md").write_text(
        textwrap.dedent(
            f"""\
            # Contract cases (Spec-grounded adversarial self-test)

            Fill every `Bxxx.py` stub: set `FILLED = True` and implement
            `run_featurelifted()`. Optionally implement `run_upstream()` with a
            symbol you discovered under `repo/` (do not use TASK entrypoints —
            none are provided).

            Then run `./{CHECKER_NAME}` from the workspace root. Do not finish
            while the checker is red. Do not hunt `public_tests/` or
            `hidden_tests/` — they are not mounted.
            """
        ),
        encoding="utf-8",
    )

    api_paths = [str(row["path"]) for row in matrix.get("required_api") or []]
    behavior_lookup = {
        str(row["id"]): str(row.get("text") or "")
        for row in matrix.get("behaviors") or []
        if isinstance(row, dict) and row.get("id")
    }
    for behavior_id in scenario_behavior_ids(matrix):
        stub_path = cases_dir / f"{behavior_id}.py"
        if stub_path.exists():
            continue
        stub_path.write_text(
            _STUB_TEMPLATE.format(
                behavior_id=behavior_id,
                required_api=api_paths,
                behavior_text=behavior_lookup.get(behavior_id, ""),
            ),
            encoding="utf-8",
        )

    checker = workspace / CHECKER_NAME
    checker.write_text(_CHECKER_SOURCE, encoding="utf-8")
    checker.chmod(0o755)

    return {
        "spec_adversarial_self_test": True,
        "matrix_file": MATRIX_FILE,
        "cases_dir": CASES_DIR,
        "checker": CHECKER_NAME,
        "behavior_stubs": scenario_behavior_ids(matrix),
        "required_api_count": len(api_paths),
    }


def task_appendix() -> str:
    return (
        "## Spec-grounded adversarial self-test\n\n"
        "This workspace includes an executable public-contract checklist. "
        "It is **not** self-reflection and **not** official benchmark tests.\n\n"
        f"1. Read `{MATRIX_FILE}` (behaviors + required_api from the public spec).\n"
        f"2. Fill every stub under `{CASES_DIR}/`: set `FILLED = True` and implement "
        "`run_featurelifted()` with boundary inputs for that Bxxx clause.\n"
        "3. Optionally implement `run_upstream()` using a symbol you find in `repo/` "
        "(no source-location hints are provided).\n"
        f"4. Run `./{CHECKER_NAME}` (optionally `--oracle-import pkg.Symbol` as a "
        "ledger hint). Fix until the checker prints `\"ok\": true`.\n"
        "5. Do **not** finish while the checker is red.\n"
        "6. Do **not** hunt `public_tests/`, `hidden_tests/`, or invent Hidden cases.\n"
        "7. Compare exception **types**, never messages.\n"
    )


def openhands_appendix() -> str:
    return (
        "Fill contract_cases/Bxxx.py stubs from contract_matrix.json, run "
        "./run_contract_check.py until ok=true, and do not finish while red. "
        "Optional upstream dual-run only via symbols you discover in repo/. "
        "Do not hunt evaluator or public/hidden benchmark tests."
    )
