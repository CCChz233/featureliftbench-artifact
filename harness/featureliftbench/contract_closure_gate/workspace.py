"""Workspace materialization and prompts for contract-closure checking."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from ..task_spec import canonical_json
from ..task_spec import compute_spec_hash
from .common import CASES_DIR
from .common import FAILURES_FILE
from .common import GENERATOR_VERSION
from .common import PUBLIC_CONTRACT_FILE
from .common import PUBLIC_CONTRACT_SCHEMA
from .common import PUBLIC_WITNESS_FILE
from .common import PUBLIC_WITNESS_SCHEMA
from .common import LITE_V1_SILENT_FINISH_ENV
from .common import WRAPPER_NAME


def _lite_v1_silent_finish(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(LITE_V1_SILENT_FINISH_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


_README = """# Public-contract behavior cases

Write Python case modules here. One case may cover multiple public behavior IDs.

Differential mode (preferred):

```python
CASE_ID = "stable-short-id"
BEHAVIOR_IDS = ["B001"]
REQUIRED_API = ["featurelifted.some_api"]
MODE = "differential"
EVIDENCE = ["public_spec:B001", "repo/path.py:10"]

def run_upstream():
    return {"result": ..., "exception": None, "state_after": ...}

def run_featurelifted():
    return {"result": ..., "exception": None, "state_after": ...}
```

Direct mode, only when there is no stable upstream pairing:

```python
CASE_ID = "stable-short-id"
BEHAVIOR_IDS = ["B002"]
REQUIRED_API = ["featurelifted.SomeClass.method"]
MODE = "direct"
EVIDENCE = ["public_spec:B002", "repo/path.py:25"]

def check_featurelifted():
    from featurelifted import SomeClass
    assert SomeClass().method() == "publicly justified value"
```

Rules:
- Cover every Bxxx behavior in PUBLIC_CONTRACT.json.
- Every REQUIRED_API value must be a published required API path.
- Cases must exercise featurelifted and fail against an empty package.
- Do not use assert True, unconditional skips, evaluator files, or hidden feedback.
- The examples above are the complete case interface; do not inspect checker or harness source.

Recommended order:
1. Run `../flb-contract-check --structure-only --summary` after implementing the API.
2. Fix compilation, imports, API paths, and signatures before writing behavior cases.
3. Run `../flb-contract-check --behavior-only --summary` after adding cases.
4. Run the full checker before finishing.
"""


_MICRO_README = """# V3 public-behavior smoke cases

Write exactly two concise Python case modules; never exceed three. One case may
map multiple public Bxxx clauses. Full clause coverage is not required.

Use the same interface as below. Prefer differential mode when the visible
upstream repository is stable and cheap to invoke:

```python
CASE_ID = "stable-short-id"
BEHAVIOR_IDS = ["B001"]
REQUIRED_API = ["featurelifted.some_api"]
MODE = "differential"
EVIDENCE = ["public_spec:B001", "repo/path.py:10"]

def run_upstream():
    return {"result": ..., "exception": None, "state_after": ...}

def run_featurelifted():
    return {"result": ..., "exception": None, "state_after": ...}
```

Use direct mode when a stable pairing is unavailable:

```python
CASE_ID = "stable-short-id"
BEHAVIOR_IDS = ["B002"]
REQUIRED_API = ["featurelifted.SomeClass.method"]
MODE = "direct"
EVIDENCE = ["public_spec:B002", "repo/path.py:25"]

def check_featurelifted():
    from featurelifted import SomeClass
    assert SomeClass().method() == "publicly justified value"
```

Prioritize checks likely to reveal implementation defects: nested or
multi-segment inputs, declared exception types, state changes, and delegation or
recursion paths. Every case must execute submission code and fail against an
empty package. Do not use assert True, unconditional skips, evaluator files, or
hidden feedback. Do not inspect the checker or harness source.

Run `../flb-contract-check --micro --summary` after implementation. Missing
Bxxx coverage is telemetry only; do not add cases merely to make coverage green.
"""


_LITE_RESCUE_PLUS_README = """# Lite Rescue+ public-behavior smoke cases

Read `../PUBLIC_WITNESS.json` and write exactly one concise direct-mode Python
case for its selected public Bxxx clause. Do this immediately after the first
structure check, before broad implementation work. Full Bxxx coverage is not
required and a missing witness is telemetry only; it never triggers a paid
evidence-completion run.

The selected public clause is the primary oracle. Encode its explicit ordering,
state transition, exception, nested result, repeated-call, reset, or roundtrip
semantic as a real assertion. Differential mode is intentionally not accepted
as the selected repair witness.

Example:

```python
CASE_ID = "stable-short-id"
BEHAVIOR_IDS = ["B002"]
REQUIRED_API = ["featurelifted.SomeClass.method"]
MODE = "direct"
EVIDENCE = ["public_spec:B002", "repo/path.py:25"]

def check_featurelifted():
    from featurelifted import SomeClass
    assert SomeClass().method() == "publicly justified value"
```

The checker gives behavior cases a shared 60-second execution budget. The
selected case must execute submission code and fail against an empty package.
Do not use assert True, unconditional skips, evaluator files, or hidden
feedback. Do not inspect checker or harness source.

Run `../flb-contract-check --lite-plus --summary` before finishing. Only a real
failure of the selected direct witness may trigger semantic repair.
"""


_WITNESS_KEYWORDS = (
    "raise",
    "error",
    "exception",
    "reject",
    "invalid",
    "ambiguous",
    "cycle",
    "expired",
    "state",
    "transition",
    "reset",
    "repeated",
    "nested",
    "ordering",
    "order",
    "roundtrip",
    "normalize",
    "dependency",
    "branch",
    "graph",
    "match",
)


def _public_witness_payload(public_spec: dict[str, Any]) -> dict[str, Any]:
    """Select one deterministic high-risk clause using public text only."""

    behaviors = [
        item
        for item in public_spec.get("behaviors", [])
        if isinstance(item, dict) and item.get("id")
    ]
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(behaviors):
        text = str(item.get("text") or "").lower()
        score = sum(1 for keyword in _WITNESS_KEYWORDS if keyword in text)
        ranked.append((-score, index, item))
    selected = min(ranked)[2] if ranked else {"id": "", "text": ""}

    def flatten(items: Any) -> list[str]:
        paths: list[str] = []
        if not isinstance(items, list):
            return paths
        for item in items:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if path:
                paths.append(path)
            paths.extend(flatten(item.get("members")))
        return paths

    payload = {
        "schema_version": PUBLIC_WITNESS_SCHEMA,
        "generator_version": GENERATOR_VERSION,
        "selection_policy": "public_keyword_risk_then_source_order.v1",
        "mode": "direct",
        "behavior_id": str(selected.get("id") or ""),
        "public_clause": str(selected.get("text") or ""),
        "candidate_required_api": flatten(public_spec.get("required_api")),
    }
    payload["witness_hash"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


_WRAPPER = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CANDIDATES = [
    Path("/flb/harness"),
    Path(__file__).resolve().parents[2] / "harness",
    Path(__file__).resolve().parents[1],
]
for candidate in CANDIDATES:
    if (candidate / "featureliftbench").is_dir():
        sys.path.insert(0, str(candidate))
        break

from featureliftbench.contract_closure_gate import check_workspace  # noqa: E402
from featureliftbench.contract_closure_gate.common import LATEST_RESULT_FILE  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="flb-contract-check")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--json-out", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--structure-only", action="store_true")
    modes.add_argument("--behavior-only", action="store_true")
    modes.add_argument("--micro", action="store_true")
    modes.add_argument("--lite-plus", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    check_mode = (
        "structure" if args.structure_only else "behavior" if args.behavior_only
        else "micro" if args.micro else "lite_plus" if args.lite_plus else "full"
    )
    try:
        result = check_workspace(args.workspace, check_mode=check_mode)
    except Exception as exc:
        print(json.dumps({"checker_error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2
    target = args.json_out or args.workspace / LATEST_RESULT_FILE
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    shown = result
    if args.summary:
        shown = {
            key: result.get(key)
            for key in (
                "check_mode", "hard_gate_ok", "behavior_gate_ok", "closure_ok",
                "repair_needed", "hard_failure_count",
                "actionable_behavior_failure_count", "soft_open_count", "unknown_count",
                "checker_environment_unknown_count",
            )
        }
        shown["failed_checks"] = [
            item for item in result.get("checks", []) if item.get("status") == "fail"
        ]
    print(json.dumps(shown, indent=2, sort_keys=True))
    return 0 if result.get("closure_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


def install_contract_closure_workspace(
    workspace_dir: str | Path,
    *,
    metadata: dict[str, Any],
    lite: bool = False,
    frozen_v1: bool = False,
    rescue: bool = False,
    rescue_plus: bool = False,
    v3: bool = False,
) -> dict[str, Any]:
    """Install only data derived from the Agent-visible public contract."""

    workspace = Path(workspace_dir).resolve()
    public_spec = metadata.get("public_spec")
    if not isinstance(public_spec, dict):
        raise ValueError("contract_closure_gate requires metadata.public_spec")
    base = {
        "schema_version": PUBLIC_CONTRACT_SCHEMA,
        "generator_version": GENERATOR_VERSION,
        "task_id": str(metadata.get("task_id") or ""),
        "spec_hash": compute_spec_hash(public_spec),
        "public_spec": public_spec,
    }
    contract_hash = hashlib.sha256(canonical_json(base).encode("utf-8")).hexdigest()
    payload = {**base, "contract_hash": contract_hash}
    serialized = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    (workspace / PUBLIC_CONTRACT_FILE).write_text(serialized, encoding="utf-8")

    witness_payload: dict[str, Any] | None = None
    if rescue_plus:
        witness_payload = _public_witness_payload(public_spec)
        (workspace / PUBLIC_WITNESS_FILE).write_text(
            json.dumps(witness_payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )

    if not lite or v3 or rescue_plus:
        cases = workspace / CASES_DIR
        cases.mkdir(parents=True, exist_ok=True)
        (cases / "README.md").write_text(
            (
                _LITE_RESCUE_PLUS_README
                if rescue_plus
                else _MICRO_README
                if v3
                else _README
            ),
            encoding="utf-8",
        )
    wrapper = workspace / WRAPPER_NAME
    wrapper.write_text(_WRAPPER, encoding="utf-8")
    wrapper.chmod(0o755)
    (workspace / "submission").mkdir(exist_ok=True)
    return {
        "contract_closure_gate": True,
        "contract_closure_gate_lite": bool(lite),
        "contract_closure_gate_lite_v1_frozen": bool(frozen_v1),
        "lite_v1_silent_finish": bool(frozen_v1 and _lite_v1_silent_finish()),
        "contract_closure_gate_lite_rescue": bool(rescue),
        "contract_closure_gate_lite_rescue_plus": bool(rescue_plus),
        "contract_closure_gate_v3": bool(v3),
        "public_contract_file": PUBLIC_CONTRACT_FILE,
        "public_witness_file": PUBLIC_WITNESS_FILE if rescue_plus else "",
        "public_witness_behavior_id": (
            witness_payload.get("behavior_id") if witness_payload else ""
        ),
        "public_contract_sha256": hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest(),
        "contract_hash": contract_hash,
        "cases_dir": CASES_DIR,
        "wrapper": WRAPPER_NAME,
    }


def task_appendix(
    *,
    lite: bool = False,
    frozen_v1: bool = False,
    rescue: bool = False,
    rescue_plus: bool = False,
    v3: bool = False,
) -> str:
    if rescue_plus:
        return (
            "## Public Contract Closure Gate Lite Rescue+\n\n"
            f"This low-token method uses only `{PUBLIC_CONTRACT_FILE}`, a structured "
            "copy of the public contract already rendered above. Evaluator tests remain "
            "hidden.\n\n"
            "1. Create an importable package immediately and cover every Required Output "
            "API with a minimal skeleton under `submission/featurelifted/`.\n"
            f"2. Run `./{WRAPPER_NAME} --structure-only --summary` by roughly step 8.\n"
            f"3. Read `{PUBLIC_WITNESS_FILE}` and immediately write exactly one direct "
            f"case under `{CASES_DIR}/` for its selected Bxxx clause by roughly step 12.\n"
            "4. Use the failing direct witness and visible upstream source to complete the "
            "implementation. Do not write differential or coverage-only cases.\n"
            f"5. Run `./{WRAPPER_NAME} --lite-plus --summary` and fix concrete structure "
            "or executable behavior mismatches. Unknown external/environmental behavior "
            "does not require repair.\n"
            "6. By roughly step 32, stop exploration. Use the remaining budget only for "
            "the final implementation, smoke check, and submission readiness.\n"
        )
    if v3:
        return (
            "## Public Contract Closure Gate V3\n\n"
            f"This method uses `{PUBLIC_CONTRACT_FILE}`, a structured copy of the public "
            "contract already rendered above. Evaluator tests remain hidden.\n\n"
            "1. Create an importable submission immediately and cover every Required "
            "Output API with a minimal skeleton within roughly 6 agent steps.\n"
            f"2. By roughly step 12, run `./{WRAPPER_NAME} --structure-only --summary`.\n"
            "3. Complete the implementation from public clauses and visible upstream "
            "source/tests.\n"
            f"4. Write exactly two concise smoke cases under `{CASES_DIR}/` (never more "
            "than three). One case may map multiple Bxxx IDs; full coverage is not required.\n"
            "5. Prioritize nested inputs, exception types, state changes, and delegation "
            "or recursion paths. Prefer stable upstream differential checks; otherwise use "
            "direct public assertions.\n"
            f"6. Run `./{WRAPPER_NAME} --micro --summary` and fix concrete structural or "
            "behavior mismatches. Missing coverage alone is telemetry, not a defect.\n"
            "7. After about 70% of the budget, stop exploration and spend the remainder "
            "only on implementation, smoke checks, and local fixes.\n"
        )
    if frozen_v1 or rescue:
        if frozen_v1 and _lite_v1_silent_finish():
            return (
                "## Public Contract Closure Gate Lite\n\n"
                f"This method uses only `{PUBLIC_CONTRACT_FILE}`, a structured "
                "copy of the public contract already rendered above. Evaluator tests remain "
                "hidden.\n\n"
                "1. Implement every Required Output API under "
                "`submission/featurelifted/`.\n"
                f"2. Run `./{WRAPPER_NAME} --structure-only --summary`.\n"
                "3. Fix compilation, import, forbidden-dependency, API-path, member, and "
                "signature findings.\n"
                "4. Do not author behavior-case files in this arm; the formal private "
                "evaluator still runs after submission.\n"
            )
        return (
            "## Public Contract Closure Gate Lite"
            + (" Rescue" if rescue else "")
            + "\n\n"
            f"This low-token method uses only `{PUBLIC_CONTRACT_FILE}`, a structured "
            "copy of the public contract already rendered above. Evaluator tests remain "
            "hidden.\n\n"
            "1. Implement every Required Output API under "
            "`submission/featurelifted/`.\n"
            f"2. Run `./{WRAPPER_NAME} --structure-only --summary`.\n"
            "3. Fix compilation, import, forbidden-dependency, API-path, member, and "
            "signature findings before finishing.\n"
            "4. Do not author behavior-case files in this arm; the formal private "
            "evaluator still runs after the structural gate.\n"
        )
    if lite:
        return (
            "## Public Contract Closure Gate Lite V2\n\n"
            f"This low-token method uses only `{PUBLIC_CONTRACT_FILE}`, a structured "
            "copy of the public contract already rendered above. Evaluator tests remain "
            "hidden.\n\n"
            "1. Before broad repository exploration, create an importable "
            "`submission/featurelifted/__init__.py`.\n"
            "2. Within roughly the first 6 agent steps, create a minimal skeleton for "
            "every Required Output API. Prefer a partial implementation over continued "
            "reading without writing.\n"
            f"3. By roughly step 12, run `./{WRAPPER_NAME} --structure-only --summary`.\n"
            "4. Fix compilation, import, forbidden-dependency, API-path, member, and "
            "signature findings before finishing.\n"
            "5. After using about 70% of the budget, stop broad exploration and spend "
            "the remaining budget only on implementation, checks, and local fixes.\n"
            "6. Do not author behavior-case files in this arm; the formal private "
            "evaluator still runs after the structural gate.\n"
        )
    return (
        "## Public Contract Closure Gate\n\n"
        f"This method uses only `{PUBLIC_CONTRACT_FILE}`, which is a structured copy "
        "of the public contract already rendered above. Evaluator tests remain hidden.\n\n"
        "During this same implementation run:\n"
        "1. Implement every Required Output API under `submission/featurelifted/`.\n"
        f"2. Run `./{WRAPPER_NAME} --structure-only --summary` and fix hard findings.\n"
        f"3. Add behavior cases under `{CASES_DIR}/` and map every public `Bxxx` ID.\n"
        "4. Prefer differential cases that compare the visible upstream repository with "
        "the lifted implementation. Use direct assertions only when pairing is unstable.\n"
        f"5. Run `./{WRAPPER_NAME} --summary` and repair actionable gaps.\n"
        "6. The checker is development evidence, not the private benchmark evaluator.\n"
    )


def openhands_appendix(
    *,
    lite: bool = False,
    frozen_v1: bool = False,
    rescue: bool = False,
    rescue_plus: bool = False,
    v3: bool = False,
) -> str:
    if rescue_plus:
        return (
            "Create the package immediately, cover all published APIs, and run the "
            "structure-only checker by about step 8. Then read "
            f"`{PUBLIC_WITNESS_FILE}` and `{CASES_DIR}/README.md`; by about step 12 write "
            "exactly one direct case for the selected Bxxx clause. Use its failing "
            "assertion to drive implementation, then run "
            f"`./{WRAPPER_NAME} --lite-plus --summary`. Do not write differential or "
            "coverage-only cases. By roughly step 32 stop repository exploration and spend all remaining "
            "steps on implementation, the smoke check, and a ready submission. Resolve "
            "only concrete findings. The selected public clause is the primary oracle. "
            "Missing witness evidence is telemetry and never causes a paid repair. Do not inspect the wrapper or "
            "`/flb/harness`.\n"
        )
    if v3:
        return (
            "Start by writing: create the package immediately, cover all published APIs "
            "within about 6 steps, and run the structure-only checker by about step 12. "
            f"After implementing, read `{CASES_DIR}/README.md`, write exactly two focused "
            "public-behavior smoke cases (never more than three), and run "
            f"`./{WRAPPER_NAME} --micro --summary`. Do not chase full Bxxx coverage. "
            "Resolve only concrete structural findings or executable behavior mismatches. "
            "Do not inspect the wrapper or `/flb/harness`.\n"
        )
    if frozen_v1 or rescue:
        if frozen_v1 and _lite_v1_silent_finish():
            return (
                "Implement the submission, then run "
                f"`./{WRAPPER_NAME} --structure-only --summary` and resolve hard "
                "findings. Do not create contract_cases or inspect the wrapper or "
                "`/flb/harness`.\n"
            )
        return (
            "Implement the submission, then run "
            f"`./{WRAPPER_NAME} --structure-only --summary` and resolve hard "
            "findings. Do not create contract_cases or inspect the wrapper or "
            "`/flb/harness`; this arm intentionally spends its budget on "
            "implementation and deterministic public API closure only.\n"
        )
    if lite:
        return (
            "Start by writing, not by exhaustively reading: create an importable package "
            "immediately, cover every published API with a minimal skeleton within about "
            "6 agent steps, and run "
            f"`./{WRAPPER_NAME} --structure-only --summary` by about step 12. Resolve hard "
            "findings, and switch to implementation-only completion mode after about 70% "
            "of the budget. "
            "Do not create contract_cases or inspect the wrapper or `/flb/harness`; this "
            "arm intentionally spends its budget on implementation and deterministic "
            "public API closure only.\n"
        )
    return (
        "Implement the submission and author public-contract behavior cases in the same run. "
        f"Read `{CASES_DIR}/README.md`, cover every Bxxx ID, and run `./{WRAPPER_NAME}` "
        "before finishing. The checker contains no benchmark evaluator tests. Its implementation "
        "is harness infrastructure and is out of scope: do not inspect the wrapper or any "
        "`/flb/harness` source. The README fully specifies the case interface.\n"
    )


def prepare_repair_workspace(
    workspace_dir: str | Path,
    *,
    check_result: dict[str, Any],
    task_markdown: str,
    lite: bool = False,
    rescue_plus: bool = False,
    repair_kind: str | None = None,
    v3: bool = False,
) -> str:
    workspace = Path(workspace_dir).resolve()
    failures = _failure_markdown(check_result)
    (workspace / FAILURES_FILE).write_text(failures, encoding="utf-8")
    base = re.sub(
        r"\n## Public Contract Closure Repair.*",
        "",
        task_markdown,
        flags=re.DOTALL,
    ).rstrip()
    if rescue_plus:
        public_contract_path = workspace / PUBLIC_CONTRACT_FILE
        public_contract = (
            public_contract_path.read_text(encoding="utf-8").strip()
            if public_contract_path.is_file()
            else base
        )
        case_readme_path = workspace / CASES_DIR / "README.md"
        case_protocol = (
            case_readme_path.read_text(encoding="utf-8").strip()
            if case_readme_path.is_file()
            else _LITE_RESCUE_PLUS_README.strip()
        )
        title = "FeatureLiftBench Targeted Public-Contract Defect Repair"
        scope = (
            "This is a defect-repair phase. Preserve unrelated code and make only "
            "the smallest public-contract implementation correction. For an executable "
            "selected-witness mismatch, treat the cited public clause as primary; correct "
            "the case only when it contradicts that clause. Missing witness evidence never "
            "starts this phase.\n\n"
        )
        action_order = (
            "2. Inspect only the directly named submission or selected direct-witness file "
            "and edit the implementation immediately. Do not add a case merely to close "
            "missing evidence; this round is reserved for an implementation defect.\n"
        )
        repaired = "".join(
            [
                f"# {title}\n\n",
                "This is a bounded continuation of an existing implementation, not a new "
                "repository-exploration task. Evaluator tests and evaluator feedback are "
                "not available. ",
                scope,
                "## Mandatory action order\n\n",
                f"1. Use the embedded `{FAILURES_FILE}` report below; do not spend a tool "
                "action reopening it, TASK.md, metadata.json, or PUBLIC_CONTRACT.json.\n",
                action_order,
                f"3. Run `./{WRAPPER_NAME} --lite-plus --summary` after the first edit. "
                "Make at most one focused correction from that output, rerun the same "
                "command, and finish.\n",
                "4. Do not run `ls`, `find`, or `tree` to inventory the workspace; do not "
                "read whole upstream modules or upstream test suites; do not install "
                "dependencies; do not inspect flb-contract-check or /flb/harness. An exact "
                "`rg` lookup in repo/ is allowed only after the first checker run and only "
                "if a public assertion cannot otherwise be justified.\n\n",
                "A passing smoke case must import and execute `submission/featurelifted`, "
                "contain a meaningful assertion, and fail against an empty package. Missing "
                "Bxxx coverage is telemetry; do not chase full coverage.\n\n",
                f"## {FAILURES_FILE}\n\n{failures.strip()}\n\n",
                f"## {PUBLIC_CONTRACT_FILE}\n\n```json\n{public_contract}\n```\n\n",
                f"## {CASES_DIR}/README.md protocol\n\n{case_protocol}\n",
            ]
        )
        (workspace / "TASK.md").write_text(repaired + "\n", encoding="utf-8")
        return repaired
    elif v3:
        appendix = (
            "## Public Contract Closure Repair (V3)\n\n"
            f"The bounded public checker found a concrete gap. Read `{FAILURES_FILE}`.\n"
            "Repair `submission/featurelifted/` from TASK.md, PUBLIC_CONTRACT.json, and "
            "repo/. Do not add cases for missing coverage and do not inspect evaluator or "
            "checker implementation. Only correct a case when its assertion is not supported "
            "by its cited public evidence.\n"
            f"Run `./{WRAPPER_NAME} --micro --summary` before finishing.\n"
        )
    elif lite:
        appendix = (
            "## Public Contract Closure Repair (Lite)\n\n"
            f"The deterministic public-contract checker found gaps. Read `{FAILURES_FILE}`.\n"
            "Repair only `submission/featurelifted/` using TASK.md, "
            "PUBLIC_CONTRACT.json, and repo/. Do not create behavior cases and do not "
            "look for evaluator tests or inspect checker implementation.\n"
            f"Run `./{WRAPPER_NAME} --structure-only --summary` before finishing.\n"
        )
    else:
        appendix = (
        "## Public Contract Closure Repair\n\n"
        f"The public-contract checker found gaps. Read `{FAILURES_FILE}`.\n"
        "Repair `submission/featurelifted/` and/or `contract_cases/` using only TASK.md, "
        "PUBLIC_CONTRACT.json, and repo/. Do not look for evaluator tests.\n"
        "Do not inspect `flb-contract-check`, `/flb/harness`, or checker implementation; "
        "`contract_cases/README.md` is the complete public case protocol. Follow the "
        "P0/P1/P2 order in the report.\n"
        f"Run `./{WRAPPER_NAME} --summary` again before finishing.\n"
        )
    repaired = base + "\n\n" + appendix
    (workspace / "TASK.md").write_text(repaired + "\n", encoding="utf-8")
    return repaired


def _failure_markdown(result: dict[str, Any]) -> str:
    hard: list[dict[str, Any]] = []
    behavior: list[dict[str, Any]] = []
    evidence_quality: list[dict[str, Any]] = []
    for item in result.get("checks", []):
        if not isinstance(item, dict) or item.get("status") == "pass":
            continue
        if item.get("severity") == "hard":
            hard.append(item)
        elif (
            item.get("category") in {"behavior", "behavior_evidence"}
            or item.get("id") == "behavior.smoke.required"
        ) and item.get("status") == "fail":
            behavior.append(item)
        else:
            evidence_quality.append(item)

    lines = [
        "# Public Contract Closure Failures",
        "",
        f"- hard_gate_ok: `{result.get('hard_gate_ok')}`",
        f"- behavior_gate_ok: `{result.get('behavior_gate_ok')}`",
        f"- closure_ok: `{result.get('closure_ok')}`",
        "",
        "Do not spend steps reading checker or harness implementation.",
    ]

    def append_group(
        title: str, intro: str, items: list[dict[str, Any]]
    ) -> None:
        if not items:
            return
        lines.extend(["", f"## {title}", "", intro, ""])
        for item in items:
            lines.append(
                f"- **{item.get('status')}** `{item.get('id')}`: "
                f"{item.get('message', '')}"
            )
            evidence = item.get("evidence")
            public_text = (
                evidence.get("public_text") if isinstance(evidence, dict) else None
            )
            if isinstance(public_text, str) and public_text.strip():
                lines.append(f"  - Public clause: {public_text.strip()}")

    append_group(
        "P0/P1 — implementation defects",
        "Fix these first, then run `./flb-contract-check --structure-only --summary`. "
        "Do not write or revise behavior cases until this section is clear.",
        hard,
    )
    append_group(
        "P2 — stable behavior mismatches",
        "Fix the implementation or the publicly justified assertion, then rerun the case.",
        behavior,
    )
    append_group(
        "P3 — evidence quality (non-repairing)",
        "These findings are telemetry and do not by themselves require repair. If time "
        "remains, one case may map multiple public IDs.",
        evidence_quality,
    )
    lines.extend(["", "The full machine result remains in the run artifacts.", ""])
    return "\n".join(lines)
