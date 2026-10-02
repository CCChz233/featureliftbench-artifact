"""Aggregate multi-reviewer Flash-33 audit runs without severity override."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from .consensus import adjudicate_records
from .schema import FLASH33_AGREEMENT_SCHEMA
from .schema import FLASH33_CONSENSUS_LABELS_SCHEMA


# Codebook severity is only used after reviewers already agree. It never
# resolves an A/B conflict.
TASK_PRIMARY_SEVERITY = {
    "underdetermined": 4,
    "ambiguous": 3,
    "recoverable": 2,
    "explicit": 1,
}

UNRESOLVED = "unresolved"
AGENT_CONSENSUS = "agent_consensus"
COVERAGE_FAILURE = "coverage_failure"


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _task_id_from_case(case_id: str, record: Mapping[str, Any] | None) -> str:
    if record and record.get("task_id"):
        return str(record["task_id"])
    parts = case_id.split("__")
    if len(parts) >= 3:
        return "__".join(parts[:-1])
    return case_id


def _test_name_from_case(case_id: str, record: Mapping[str, Any] | None) -> str:
    if record and record.get("nodeid"):
        nodeid = str(record["nodeid"])
        if "::" in nodeid:
            return nodeid.rsplit("::", 1)[-1]
    if "__" in case_id:
        return case_id.rsplit("__", 1)[-1]
    return case_id


def _citation_status(record: Mapping[str, Any] | None, *, valid: bool) -> str:
    if not valid or record is None:
        return "invalid"
    evidence = record.get("evidence") or []
    if evidence:
        return "present"
    return "empty"


def load_reviewer_run(run_dir: Path, reviewer: str) -> dict[str, dict[str, Any]]:
    """Load one reviewer directory keyed by case_id."""

    cases: dict[str, dict[str, Any]] = {}
    run_summary = _load_json(run_dir / "run.json")
    default_agent_id = reviewer
    if isinstance(run_summary, dict) and run_summary.get("agent_id"):
        default_agent_id = str(run_summary["agent_id"])
    for validation_path in sorted(run_dir.glob("*/validation.json")):
        case_id = validation_path.parent.name
        validation = _load_json(validation_path)
        if not isinstance(validation, dict):
            cases[case_id] = {
                "case_id": case_id,
                "reviewer": reviewer,
                "valid": False,
                "coverage_failure": True,
                "validation_errors": ["invalid validation.json"],
                "record": None,
                "agent_id": default_agent_id,
                "verdict": None,
                "confidence": None,
                "citation_status": "invalid",
            }
            continue
        record_payload = _load_json(validation_path.parent / "audit_record.json")
        record = record_payload if isinstance(record_payload, dict) else None
        valid = bool(validation.get("valid")) and record is not None
        errors = [str(item) for item in (validation.get("errors") or [])]
        if record is None:
            errors = errors or ["missing audit_record.json"]
        agent_id = str(
            (record or {}).get("agent_id")
            or validation.get("agent_id")
            or default_agent_id
        )
        cases[case_id] = {
            "case_id": case_id,
            "reviewer": reviewer,
            "valid": valid,
            "coverage_failure": not valid,
            "validation_errors": errors,
            "record": record,
            "agent_id": agent_id,
            "verdict": str(record["verdict"]).lower() if record and record.get("verdict") else None,
            "confidence": record.get("confidence") if record else None,
            "citation_status": _citation_status(record, valid=valid),
        }
    return cases


def _classify_consensus(
    reviewer_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    valid_rows = [row for row in reviewer_rows if row["valid"] and row["record"]]
    missing = [row["reviewer"] for row in reviewer_rows if row["coverage_failure"]]
    if missing:
        return {
            "consensus_status": COVERAGE_FAILURE,
            "consensus_verdict": UNRESOLVED,
            "abstain_reason": (
                "audit coverage failure: invalid or missing records from "
                + ", ".join(missing)
            ),
            "adjudication": None,
        }
    if len(valid_rows) < 2:
        return {
            "consensus_status": "insufficient_reviewers",
            "consensus_verdict": UNRESOLVED,
            "abstain_reason": f"need two valid reviewer records, have {len(valid_rows)}",
            "adjudication": None,
        }

    adjudication = adjudicate_records(row["record"] for row in valid_rows)
    verdict = str(adjudication.get("verdict") or "abstain")
    reason = str(adjudication.get("abstain_reason") or "")
    if verdict != "abstain":
        return {
            "consensus_status": AGENT_CONSENSUS,
            "consensus_verdict": verdict,
            "abstain_reason": "",
            "adjudication": adjudication,
        }
    if "no verdict reached" in reason:
        labels = {str(row["verdict"]) for row in valid_rows}
        if labels == {"abstain"}:
            status = "abstain"
            consensus_verdict = "abstain"
        else:
            status = "conflict"
            consensus_verdict = UNRESOLVED
        return {
            "consensus_status": status,
            "consensus_verdict": consensus_verdict,
            "abstain_reason": reason,
            "adjudication": adjudication,
        }
    if "share a reproducible" in reason:
        status = "citation_mismatch"
    elif "confidence" in reason:
        status = "low_confidence"
    else:
        status = UNRESOLVED
    return {
        "consensus_status": status,
        "consensus_verdict": UNRESOLVED,
        "abstain_reason": reason,
        "adjudication": adjudication,
    }


def _task_primary(assertions: list[dict[str, Any]]) -> str:
    if any(item.get("consensus_status") != AGENT_CONSENSUS for item in assertions):
        return UNRESOLVED
    return max(
        assertions,
        key=lambda item: TASK_PRIMARY_SEVERITY.get(str(item.get("label")), -1),
    )["label"]


def aggregate_reviewer_runs(
    runs: Iterable[tuple[str, Path]],
    *,
    suite_manifest: Path | None = None,
) -> dict[str, Any]:
    """Aggregate two or more reviewer runs into assertion-level consensus."""

    run_list = [(reviewer, Path(run_dir)) for reviewer, run_dir in runs]
    loaded: list[tuple[str, dict[str, dict[str, Any]]]] = [
        (reviewer, load_reviewer_run(run_dir, reviewer))
        for reviewer, run_dir in run_list
    ]

    case_meta: dict[str, dict[str, Any]] = {}
    if suite_manifest and suite_manifest.is_file():
        manifest = _load_json(suite_manifest)
        if isinstance(manifest, dict):
            for row in manifest.get("cases") or []:
                if isinstance(row, dict) and row.get("case_id"):
                    case_meta[str(row["case_id"])] = row

    case_ids = sorted({case_id for _, cases in loaded for case_id in cases})
    if suite_manifest and case_meta:
        case_ids = sorted(set(case_ids) | set(case_meta))

    assertions: list[dict[str, Any]] = []
    for case_id in case_ids:
        reviewer_rows: list[dict[str, Any]] = []
        for reviewer, cases in loaded:
            row = cases.get(case_id)
            if row is None:
                reviewer_rows.append(
                    {
                        "case_id": case_id,
                        "reviewer": reviewer,
                        "valid": False,
                        "coverage_failure": True,
                        "validation_errors": ["missing reviewer run"],
                        "record": None,
                        "agent_id": reviewer,
                        "verdict": None,
                        "confidence": None,
                        "citation_status": "invalid",
                    }
                )
            else:
                reviewer_rows.append(row)
        classified = _classify_consensus(reviewer_rows)
        record = next(
            (row["record"] for row in reviewer_rows if row["record"] is not None),
            None,
        )
        meta = case_meta.get(case_id) or {}
        task_id = str(meta.get("task_id") or _task_id_from_case(case_id, record))
        test_name = str(
            meta.get("test_name") or _test_name_from_case(case_id, record)
        )
        adjudication = classified["adjudication"] or {}
        shared_citations = list(adjudication.get("evidence") or [])
        if classified["consensus_status"] == AGENT_CONSENSUS and not shared_citations:
            citation_status = "not_required"
        elif shared_citations:
            citation_status = "shared"
        elif all(row["citation_status"] == "present" for row in reviewer_rows):
            citation_status = "unshared"
        else:
            citation_status = "missing"
        assertions.append(
            {
                "case_id": case_id,
                "task_id": task_id,
                "test": test_name,
                "nodeid": (record or {}).get("nodeid") or meta.get("nodeid"),
                "label": classified["consensus_verdict"],
                "consensus_status": classified["consensus_status"],
                "abstain_reason": classified["abstain_reason"],
                "reviewers": [
                    {
                        "reviewer": row["reviewer"],
                        "agent_id": row["agent_id"],
                        "valid": row["valid"],
                        "verdict": row["verdict"],
                        "confidence": row["confidence"],
                        "citation_status": row["citation_status"],
                        "errors": row["validation_errors"],
                    }
                    for row in reviewer_rows
                ],
                "shared_citation_count": len(shared_citations),
                "citation_status": citation_status,
            }
        )

    by_task: dict[str, list[dict[str, Any]]] = {}
    for assertion in assertions:
        by_task.setdefault(str(assertion["task_id"]), []).append(assertion)

    labels: list[dict[str, Any]] = []
    for task_id in sorted(by_task):
        task_assertions = by_task[task_id]
        task_primary = _task_primary(task_assertions)
        labels.append(
            {
                "task_id": task_id,
                "failed_hidden_tests": [item["test"] for item in task_assertions],
                "task_primary": task_primary,
                "assertions": task_assertions,
                "confidence": (
                    "agent_consensus"
                    if task_primary not in {UNRESOLVED, "abstain"}
                    else "unresolved"
                ),
                "gold": False,
            }
        )

    status_counts = Counter(str(item["consensus_status"]) for item in assertions)
    valid_reviewer_rows = sum(
        1
        for item in assertions
        for reviewer in item["reviewers"]
        if reviewer["valid"]
    )
    total_reviewer_rows = sum(len(item["reviewers"]) for item in assertions) or 1
    agreeing = status_counts.get(AGENT_CONSENSUS, 0)
    conflicts = status_counts.get("conflict", 0)
    coverage = status_counts.get(COVERAGE_FAILURE, 0)
    shared_citation_cases = sum(
        1 for item in assertions if item["citation_status"] == "shared"
    )
    primary_counts = Counter(str(item["task_primary"]) for item in labels)
    agreement = {
        "schema_version": FLASH33_AGREEMENT_SCHEMA,
        "slice": "hidden_provenance_flash33_v1",
        "generated_at": date.today().isoformat(),
        "gold": False,
        "n_cases": len(assertions),
        "n_tasks": len(labels),
        "n_reviewers": len(loaded),
        "valid_rate": round(valid_reviewer_rows / total_reviewer_rows, 6),
        "agreement": agreeing,
        "conflict": conflicts,
        "abstain": status_counts.get("abstain", 0),
        "coverage_failure": coverage,
        "citation_coverage": round(shared_citation_cases / len(assertions), 6)
        if assertions
        else 0.0,
        "consensus_status_counts": dict(sorted(status_counts.items())),
        "reviewers": [reviewer for reviewer, _ in run_list],
        "cases": [
            {
                "case_id": item["case_id"],
                "task_id": item["task_id"],
                "consensus_status": item["consensus_status"],
                "consensus_verdict": item["label"],
                "citation_status": item["citation_status"],
                "abstain_reason": item["abstain_reason"],
                "reviewers": item["reviewers"],
            }
            for item in assertions
        ],
    }
    consensus = {
        "schema_version": FLASH33_CONSENSUS_LABELS_SCHEMA,
        "slice": "hidden_provenance_flash33_v1",
        "generated_at": date.today().isoformat(),
        "labeling": {
            "codebook": "docs/HIDDEN_CONTRACT_PROVENANCE.md",
            "reviewers": [reviewer for reviewer, _ in run_list],
            "gold": False,
            "note": (
                "Agent-adjudicated dual-reviewer consensus. Not human gold. "
                "Conflicts, invalid records, and missing records are unresolved "
                "coverage or agreement failures; severity never overrides a conflict."
            ),
            "runs": [
                {"reviewer": reviewer, "run_dir": str(run_dir.resolve())}
                for reviewer, run_dir in run_list
            ],
            "suite_manifest": str(suite_manifest.resolve()) if suite_manifest else None,
        },
        "n": len(labels),
        "counts": {
            "explicit": int(primary_counts.get("explicit", 0)),
            "recoverable": int(primary_counts.get("recoverable", 0)),
            "ambiguous": int(primary_counts.get("ambiguous", 0)),
            "underdetermined": int(primary_counts.get("underdetermined", 0)),
            "abstain": int(primary_counts.get("abstain", 0)),
            "unresolved": int(primary_counts.get(UNRESOLVED, 0)),
        },
        "agreement": {
            "valid_rate": agreement["valid_rate"],
            "agreement": agreeing,
            "conflict": conflicts,
            "abstain": agreement["abstain"],
            "coverage_failure": coverage,
            "citation_coverage": agreement["citation_coverage"],
        },
        "labels": labels,
    }
    return {"consensus": consensus, "agreement": agreement}


def write_aggregate(
    result: Mapping[str, Any],
    *,
    output: Path,
    agreement_output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    agreement_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_json_text(result["consensus"]), encoding="utf-8")
    agreement_output.write_text(_json_text(result["agreement"]), encoding="utf-8")
