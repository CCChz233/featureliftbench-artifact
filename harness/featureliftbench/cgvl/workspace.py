"""Workspace install + prompt appendix for CGVL."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from .common import CASES_DIR
from .common import CHECKER_NAME
from .common import EVIDENCE_FILE
from .common import MATRIX_FILE
from .expand import build_cgvl_matrix
from .expand import required_cells


def _stub_source(cell: dict[str, Any]) -> str:
    cell_id = str(cell.get("id") or "")
    return (
        f'"""CGVL cell {cell_id}. Fill a discriminating probe through the public entry."""\n'
        "\n"
        f"CELL_ID = {cell_id!r}\n"
        f"CLAUSE = {str(cell.get('clause') or '')!r}\n"
        f"PUBLIC_ENTRY = {str(cell.get('public_entry') or '')!r}\n"
        f"PUBLIC_ENTRIES = {list(cell.get('public_entries') or [])!r}\n"
        f"ROLE = {str(cell.get('role') or '')!r}\n"
        f"INPUT_VARIANT = {str(cell.get('input_variant') or '')!r}\n"
        f"REQUIRED_VARIANTS = {list(cell.get('required_variants') or [])!r}\n"
        f"REQUIRED_MUTANTS = {list(cell.get('required_mutants') or [])!r}\n"
        f"EXPECTED_EXCEPTION = {str(cell.get('expected_exception') or '')!r}\n"
        f"MIN_ASSERTIONS = {int(cell.get('min_assertions') or 1)!r}\n"
        f"MIN_PUBLIC_ENTRIES = {int(cell.get('min_public_entries') or 1)!r}\n"
        "\n"
        "# Set True after implementing a real probe (not a placeholder).\n"
        "FILLED = False\n"
        "# Set True only when TASK + repo cannot uniquely determine the oracle.\n"
        "UNDETERMINED = False\n"
        "\n"
        "def check(name, actual, expected):\n"
        "    passed = actual == expected\n"
        "    assert passed, f'{name}: {actual!r} != {expected!r}'\n"
        "    return {'name': name, 'actual': actual, 'expected': expected, 'passed': passed}\n"
        "\n"
        "\n"
        "def counterexample(mutant_id, observed, mutant_expected, witness):\n"
        "    # The checker recomputes killed; a declaration alone is not accepted.\n"
        "    return {\n"
        "        'mutant_id': mutant_id,\n"
        "        'observed': observed,\n"
        "        'mutant_expected': mutant_expected,\n"
        "        'witness': witness,\n"
        "    }\n"
        "\n"
        "\n"
        "def run_featurelifted():\n"
        '    """Call PUBLIC_ENTRY on submission/featurelifted.\n'
        "\n"
        "    Return dict with assertions and executable counterexamples.\n"
        "    Required keys: assertions, counterexamples, covered_variants.\n"
        "    State guards also return state_before and state_after.\n"
        "    Compare exception types only — never messages.\n"
        "    Do not call an internal helper instead of PUBLIC_ENTRY.\n"
        '    """\n'
        f"    raise NotImplementedError({f'fill run_featurelifted for {cell_id}'!r})\n"
    )


_CHECKER_SOURCE = r'''#!/usr/bin/env python3
"""CGVL gate: public-entry discriminating cells. No Hidden / public_tests."""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _symbol(path: str) -> str:
    return path.rsplit(".", 1)[-1]


def _expr_path(
    node: ast.AST,
    aliases: dict[str, str],
    instances: dict[str, str],
) -> str:
    if isinstance(node, ast.Name):
        return instances.get(node.id) or aliases.get(node.id) or node.id
    if isinstance(node, ast.Attribute):
        parent = _expr_path(node.value, aliases, instances)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _expr_path(node.func, aliases, instances)
    return ""


def _public_entries_called(source: str) -> set[str]:
    """Resolve exact featurelifted call paths, including instance methods."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    aliases: dict[str, str] = {"featurelifted": "featurelifted"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "featurelifted" or alias.name.startswith("featurelifted."):
                    aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "featurelifted" or node.module.startswith("featurelifted."):
                for alias in node.names:
                    if alias.name != "*":
                        aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    instances: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        constructor = _expr_path(value.func, aliases, instances)
        if not constructor.startswith("featurelifted."):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                instances[target.id] = constructor

    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        path = _expr_path(node.func, aliases, instances)
        if path.startswith("featurelifted."):
            called.add(path)
    return called


def _resolve_path(path: str) -> Any:
    parts = path.split(".")
    if len(parts) < 2:
        raise ImportError(f"invalid API path: {path}")
    value: Any = importlib.import_module(parts[0])
    for part in parts[1:]:
        value = getattr(value, part)
    return value


def _normalize(obs: Any) -> dict[str, Any]:
    if not isinstance(obs, dict):
        raise TypeError(f"observation must be a dict, got {type(obs).__name__}")
    exception = obs.get("exception_type")
    if isinstance(exception, type) and issubclass(exception, BaseException):
        exception = exception.__name__
    return {
        "result": _json_stable(obs.get("result")),
        "exception_type": exception,
        "state": _json_stable(obs.get("state")),
        "state_before": _json_stable(obs.get("state_before")),
        "state_after": _json_stable(obs.get("state_after")),
        "assertions": _json_stable(obs.get("assertions")),
        "counterexamples": _json_stable(obs.get("counterexamples")),
        "covered_variants": _json_stable(obs.get("covered_variants")),
        "oracle_source": str(obs.get("oracle_source") or ""),
    }


def _json_stable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_stable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_stable(item) for item in value]
    return repr(value)


def _has_executable_assert(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.Assert) for node in ast.walk(tree))


def _validate_assertions(obs: dict[str, Any], minimum: int) -> tuple[list[dict[str, Any]], str]:
    raw = obs.get("assertions")
    rows = raw if isinstance(raw, list) else []
    if len(rows) < minimum:
        return [], f"expected at least {minimum} explicit assertion records"
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            return [], f"assertion {index} is not a dict"
        if not str(item.get("name") or "").strip():
            return [], f"assertion {index} has no name"
        if "actual" not in item or "expected" not in item:
            return [], f"assertion {index} must record actual and expected"
        passed = item.get("passed")
        recomputed = item.get("actual") == item.get("expected")
        if passed is not True or not recomputed:
            return [], f"assertion {index} is not a passing actual/expected comparison"
        normalized.append(dict(item))
    return normalized, ""


def _validate_counterexamples(
    obs: dict[str, Any],
    allowed: set[str],
) -> tuple[list[str], str]:
    raw = obs.get("counterexamples")
    rows = raw if isinstance(raw, list) else []
    killed: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        mutant_id = str(item.get("mutant_id") or "")
        if mutant_id not in allowed:
            continue
        witness = str(item.get("witness") or "").strip()
        if not witness:
            continue
        if "observed" not in item or "mutant_expected" not in item:
            continue
        if item.get("observed") != item.get("mutant_expected"):
            killed.append(mutant_id)
    if allowed and not killed:
        return [], "no executable counterexample rejects a required failure mode"
    return sorted(set(killed)), ""


def _load_case(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"flb_cgvl_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _purge_featurelifted_modules() -> None:
    for name in list(sys.modules):
        if name == "featurelifted" or name.startswith("featurelifted."):
            sys.modules.pop(name, None)


def _append_ledger(workspace: Path, payload: dict[str, Any]) -> None:
    ledger = workspace / "agent" / "cgvl_check.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def check_isolation_surface(workspace: Path, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    forbidden = {
        str(item).strip()
        for item in (matrix.get("forbidden_imports") or [])
        if str(item).strip()
    }
    hits: list[str] = []
    package = workspace / "submission" / "featurelifted"
    for path in sorted(package.rglob("*.py")) if package.is_dir() else []:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            hits.append(f"{path.name}: cannot scan: {type(exc).__name__}: {exc}")
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            for name in names:
                if any(name == item or name.startswith(f"{item}.") for item in forbidden):
                    hits.append(f"{path.name}:{getattr(node, 'lineno', 0)} imports {name}")
            if isinstance(node, ast.Call) and node.args:
                dynamic = (
                    isinstance(node.func, ast.Name) and node.func.id == "__import__"
                ) or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                )
                first = node.args[0]
                if dynamic and isinstance(first, ast.Constant) and isinstance(first.value, str):
                    name = first.value
                    if any(name == item or name.startswith(f"{item}.") for item in forbidden):
                        hits.append(
                            f"{path.name}:{getattr(node, 'lineno', 0)} dynamically imports {name}"
                        )
    return [
        {
            "row_kind": "isolation",
            "id": str(matrix.get("isolation_behavior_id") or "forbidden_imports"),
            "ok": not hits,
            "forbidden_imports": sorted(forbidden),
            "hits": hits,
            "error": "; ".join(hits[:8]),
        }
    ]


def check_import_surface(workspace: Path, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    submission = workspace / "submission"
    if str(submission) not in sys.path:
        sys.path.insert(0, str(submission))
    rows: list[dict[str, Any]] = []
    for entry in matrix.get("required_api") or []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if not path:
            continue
        ok = False
        error = ""
        try:
            _resolve_path(path)
            ok = True
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        rows.append({"row_kind": "required_api", "id": path, "ok": ok, "error": error})
    return rows


def check_cells(workspace: Path, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    cases_dir = workspace / "cgvl_cells"
    submission = workspace / "submission"
    if str(submission) not in sys.path:
        sys.path.insert(0, str(submission))
    rows: list[dict[str, Any]] = []
    for cell in matrix.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        cell_id = str(cell.get("id") or "")
        required = bool(cell.get("required"))
        case_path = cases_dir / f"{cell_id}.py"
        row: dict[str, Any] = {
            "row_kind": "cell",
            "id": cell_id,
            "role": cell.get("role"),
            "ok": False,
            "filled": False,
            "undetermined": False,
            "public_entry_called": False,
            "public_entries_called": [],
            "assertions": [],
            "mutants_killed": [],
            "error": "",
        }
        if not case_path.is_file():
            row["error"] = f"missing cell {case_path.name}"
            if not required:
                row["ok"] = True
            rows.append(row)
            continue
        source = case_path.read_text(encoding="utf-8")
        try:
            _purge_featurelifted_modules()
            module = _load_case(case_path)
            filled = bool(getattr(module, "FILLED", False))
            undetermined = bool(getattr(module, "UNDETERMINED", False))
            row["filled"] = filled
            row["undetermined"] = undetermined
            public_entry = str(cell.get("public_entry") or "")
            allowed_entries = {
                str(item)
                for item in (cell.get("public_entries") or [public_entry])
                if str(item)
            }
            called_entries = _public_entries_called(source)
            matched_entries = sorted(called_entries & allowed_entries)
            row["public_entries_called"] = matched_entries
            minimum_entries = int(cell.get("min_public_entries") or 1)
            row["public_entry_called"] = len(matched_entries) >= minimum_entries
            if undetermined and cell.get("undetermined"):
                row["ok"] = True
                row["error"] = "marked undetermined; not counted as a guessed oracle"
                rows.append(row)
                continue
            if not filled:
                row["error"] = "FILLED is False"
                rows.append(row)
                continue
            if required and not row["public_entry_called"]:
                row["error"] = (
                    f"probe must call at least {minimum_entries} exact harness-owned "
                    "public entry paths from: "
                    + ", ".join(sorted(allowed_entries))
                )
                rows.append(row)
                continue
            if required and not _has_executable_assert(source):
                row["error"] = "probe contains no executable assert statement"
                rows.append(row)
                continue
            obs = _normalize(module.run_featurelifted())
            row["featurelifted"] = obs
            if obs.get("exception_type") == "NotImplementedError":
                row["error"] = "run_featurelifted still raises NotImplementedError"
                rows.append(row)
                continue
            role = str(cell.get("role") or "")
            assertions, assertion_error = _validate_assertions(
                obs,
                int(cell.get("min_assertions") or 1),
            )
            row["assertions"] = assertions
            if required and assertion_error:
                row["error"] = assertion_error
                rows.append(row)
                continue
            expected_exc = str(cell.get("expected_exception") or "")
            if role == "negative" and not cell.get("undetermined"):
                observed_exc = str(obs.get("exception_type") or "")
                if not observed_exc:
                    row["error"] = "negative cell did not observe a declared exception type"
                    rows.append(row)
                    continue
                if expected_exc and observed_exc != expected_exc:
                    row["error"] = (
                        f"negative cell expected {expected_exc}, got {observed_exc}"
                    )
                    rows.append(row)
                    continue
            if role == "state_guard":
                before = obs.get("state_before")
                after = obs.get("state_after")
                if before is None or after is None:
                    row["error"] = "state_guard must return state_before and state_after"
                    rows.append(row)
                    continue
                if before != after:
                    row["error"] = "state_guard changed public state after a failed operation"
                    rows.append(row)
                    continue
            required_variants = {
                str(item) for item in (cell.get("required_variants") or []) if str(item)
            }
            covered_variants = {
                str(item) for item in (obs.get("covered_variants") or []) if str(item)
            }
            if required_variants and not required_variants.issubset(covered_variants):
                missing = sorted(required_variants - covered_variants)
                row["error"] = "missing declared union-arm probes: " + ", ".join(missing)
                rows.append(row)
                continue
            allowed = set(cell.get("required_mutants") or [])
            killed, counterexample_error = _validate_counterexamples(obs, allowed)
            row["mutants_killed"] = killed
            if required and counterexample_error:
                row["error"] = counterexample_error + ": " + ", ".join(sorted(allowed))
                rows.append(row)
                continue
            row["ok"] = True
        except NotImplementedError as exc:
            row["error"] = f"NotImplementedError: {exc}"
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["traceback"] = traceback.format_exc(limit=4)
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    matrix_path = workspace / "cgvl_matrix.json"
    if not matrix_path.is_file():
        print(f"missing {matrix_path}", file=sys.stderr)
        return 2
    matrix = _load_json(matrix_path)
    api_rows = check_import_surface(workspace, matrix)
    isolation_rows = check_isolation_surface(workspace, matrix)
    cell_rows = check_cells(workspace, matrix)
    all_rows = api_rows + isolation_rows + cell_rows
    ok = all(bool(row.get("ok")) for row in api_rows + isolation_rows) and all(
        bool(row.get("ok")) for row in cell_rows if row.get("id")
    )
    evidence = {
        "clause": [row.get("id") for row in cell_rows],
        "public_entry": [
            row.get("id") for row in cell_rows if row.get("public_entry_called")
        ],
        "closed": [row.get("id") for row in cell_rows if row.get("ok")],
        "open": [
            row.get("id")
            for row in cell_rows
            if not row.get("ok") and not row.get("undetermined")
        ],
    }
    payload = {
        "ok": ok,
        "api_rows": api_rows,
        "isolation_rows": isolation_rows,
        "cell_rows": cell_rows,
        "red_count": sum(1 for row in all_rows if not row.get("ok")),
        "green_count": sum(1 for row in all_rows if row.get("ok")),
        "evidence": evidence,
        "finish_allowed": ok,
    }
    (workspace / "cgvl_evidence.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _append_ledger(workspace, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def install_cgvl_workspace(
    workspace_dir: str | Path,
    *,
    public_spec: dict[str, Any],
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    matrix = build_cgvl_matrix(public_spec)
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
            # CGVL cells

            The harness generated these slots from TASK / public_spec. Do not add
            or delete rows in `{MATRIX_FILE}`. Fill each `{CASES_DIR}/C*.py`:

            1. Call at least `MIN_PUBLIC_ENTRIES` harness-owned paths exactly.
            2. Record named actual/expected assertions and execute Python `assert`.
            3. Return executable counterexamples; declarations alone do not close a row.
            4. Cover every `REQUIRED_VARIANTS` value in the same compact cell.
            5. State guards must return equal `state_before` and `state_after`.
            6. If the exact oracle cannot be uniquely determined from TASK, set
               `UNDETERMINED = True` instead of guessing.

            Then run `./{CHECKER_NAME}` until it prints `"ok": true`.
            Do not hunt `public_tests/` or `hidden_tests/`.
            """
        ),
        encoding="utf-8",
    )
    for cell in matrix.get("cells") or []:
        if not isinstance(cell, dict) or not cell.get("id"):
            continue
        stub_path = cases_dir / f"{cell['id']}.py"
        if stub_path.exists():
            continue
        stub_path.write_text(_stub_source(cell), encoding="utf-8")
    checker = workspace / CHECKER_NAME
    checker.write_text(_CHECKER_SOURCE, encoding="utf-8")
    checker.chmod(0o755)
    (workspace / EVIDENCE_FILE).write_text(
        json.dumps({"ok": False, "finish_allowed": False, "note": "run checker"}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {
        "cgvl": True,
        "matrix_file": MATRIX_FILE,
        "cases_dir": CASES_DIR,
        "checker": CHECKER_NAME,
        "cell_count": len(matrix.get("cells") or []),
        "required_cell_count": len(required_cells(matrix)),
    }


def task_appendix() -> str:
    return (
        "## Contract-Guided Verification Loop (CGVL)\n\n"
        "This workspace contains a **harness-generated** contract coverage matrix. "
        "You may fill tests; you may not invent, drop, or rewrite slots.\n\n"
        f"1. Read `{MATRIX_FILE}` before browsing `repo/` for implementation details.\n"
        f"2. Fill every required cell under `{CASES_DIR}/` through an exact listed "
        "`PUBLIC_ENTRIES` paths and satisfy `MIN_PUBLIC_ENTRIES` (no internal-helper-only probes).\n"
        "3. Each cell must execute named actual/expected assertions. Returning flags "
        "without asserting them remains red.\n"
        "4. Return executable counterexamples for a listed failure mode; the checker "
        "recomputes whether the witness is discriminating.\n"
        "5. Cover every union arm in a compact parameter cell, and compare state_before "
        "with state_after for no-op failure contracts.\n"
        "6. The checker scans submission imports against the public isolation contract.\n"
        "7. If TASK cannot uniquely determine an oracle, set `UNDETERMINED = True` "
        "and stop guessing.\n"
        "8. Allocate remaining steps to uncovered required cells. Do not spend the "
        "budget copying unrelated upstream packages.\n"
        f"9. Run `./{CHECKER_NAME}` until `ok` is true. The runtime rejects a red finish.\n"
        "10. Do **not** hunt `public_tests/` or `hidden_tests/`.\n"
        "11. Compare exception **types**, never messages.\n"
    )


def openhands_appendix() -> str:
    return (
        "Fill compact behavior cells with exact public-entry calls, executable "
        "actual/expected assertions, counterexample witnesses, and isolation-safe code. "
        "Run ./run_cgvl_check.py until ok=true; the runtime rejects a red finish. "
        "Do not replace the harness matrix with self-authored clauses. "
        "Do not hunt evaluator or public/hidden benchmark tests."
    )
