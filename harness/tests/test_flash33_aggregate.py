from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.agentic_evidence import AUDIT_RECORD_SCHEMA
from featureliftbench.agentic_evidence import build_citation
from featureliftbench.agentic_evidence.flash33_aggregate import (
    aggregate_reviewer_runs,
)


def _task(root: Path) -> Path:
    task = root / "demo"
    (task / "repo" / "pkg").mkdir(parents=True)
    (task / "TASK.md").write_text("# Demo\n\nNormalize text.\n", encoding="utf-8")
    (task / "metadata.json").write_text(
        json.dumps(
            {"public_spec": {"behaviors": [{"id": "B001", "text": "Normalize text."}]}}
        )
        + "\n",
        encoding="utf-8",
    )
    (task / "repo" / "pkg" / "normalize.py").write_text(
        "def normalize(value: str) -> str:\n    return value.casefold()\n",
        encoding="utf-8",
    )
    return task


def _record(
    *,
    agent_id: str,
    citation: dict,
    verdict: str = "explicit",
    task_id: str = "aiohttp__url_params_core__hard3_001",
    nodeid: str = "evaluator_assertion::test_invalid_header_name_raises",
    confidence: float = 0.9,
) -> dict:
    evidence = [citation] if verdict in {"explicit", "recoverable", "ambiguous"} else []
    counter = [citation] if verdict == "ambiguous" else []
    return {
        "schema_version": AUDIT_RECORD_SCHEMA,
        "task_id": task_id,
        "nodeid": nodeid,
        "agent_id": agent_id,
        "verdict": verdict,
        "confidence": confidence,
        "public_obligation_ids": ["B001"],
        "evidence": evidence,
        "counterevidence": counter,
        "abstain_reason": "cannot decide" if verdict == "abstain" else "",
    }


def _write_run(
    root: Path,
    *,
    reviewer: str,
    case_id: str,
    record: dict | None,
    valid: bool,
    errors: list[str] | None = None,
) -> Path:
    run = root / reviewer
    case = run / case_id
    case.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps({"agent_id": reviewer, "case_count": 1}) + "\n",
        encoding="utf-8",
    )
    if record is not None:
        (case / "audit_record.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
    (case / "validation.json").write_text(
        json.dumps(
            {
                "case_id": case_id,
                "agent_id": reviewer,
                "valid": valid,
                "errors": errors or ([] if valid else ["invalid record"]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return run


class Flash33AggregateTests(unittest.TestCase):
    def test_agreement_with_shared_citation_is_agent_consensus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            citation = build_citation(
                _task(root / "task"),
                path="TASK.md",
                kind="task",
                start_line=1,
                end_line=1,
                claim="The task names the behavior.",
            )
            case_id = "aiohttp__url_params_core__hard3_001__test_invalid_header_name_raises"
            a = _write_run(
                root,
                reviewer="auditor_a",
                case_id=case_id,
                record=_record(agent_id="auditor_a", citation=citation),
                valid=True,
            )
            b = _write_run(
                root,
                reviewer="auditor_b",
                case_id=case_id,
                record=_record(agent_id="auditor_b", citation=citation),
                valid=True,
            )
            result = aggregate_reviewer_runs(
                [("auditor_a", a), ("auditor_b", b)]
            )
            assertion = result["consensus"]["labels"][0]["assertions"][0]
            self.assertEqual(assertion["consensus_status"], "agent_consensus")
            self.assertEqual(assertion["label"], "explicit")
            self.assertEqual(result["consensus"]["labels"][0]["task_primary"], "explicit")
            self.assertEqual(result["agreement"]["agreement"], 1)
            self.assertEqual(result["agreement"]["conflict"], 0)

    def test_label_conflict_is_unresolved_not_max_severity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            citation = build_citation(
                _task(root / "task"),
                path="TASK.md",
                kind="task",
                start_line=1,
                end_line=1,
                claim="The task names the behavior.",
            )
            case_id = "distlib__wheel_metadata_core__hard3_001__test_validate_record_hash"
            a = _write_run(
                root,
                reviewer="auditor_a",
                case_id=case_id,
                record=_record(
                    agent_id="auditor_a",
                    citation=citation,
                    verdict="explicit",
                    task_id="distlib__wheel_metadata_core__hard3_001",
                    nodeid="evaluator_assertion::test_validate_record_hash",
                ),
                valid=True,
            )
            b = _write_run(
                root,
                reviewer="auditor_b",
                case_id=case_id,
                record=_record(
                    agent_id="auditor_b",
                    citation=citation,
                    verdict="underdetermined",
                    task_id="distlib__wheel_metadata_core__hard3_001",
                    nodeid="evaluator_assertion::test_validate_record_hash",
                ),
                valid=True,
            )
            result = aggregate_reviewer_runs(
                [("auditor_a", a), ("auditor_b", b)]
            )
            label = result["consensus"]["labels"][0]
            assertion = label["assertions"][0]
            self.assertEqual(assertion["reviewers"][0]["verdict"], "explicit")
            self.assertEqual(assertion["reviewers"][1]["verdict"], "underdetermined")
            self.assertEqual(assertion["consensus_status"], "conflict")
            self.assertEqual(assertion["label"], "unresolved")
            self.assertEqual(label["task_primary"], "unresolved")
            self.assertEqual(result["consensus"]["counts"]["underdetermined"], 0)
            self.assertEqual(result["consensus"]["counts"]["unresolved"], 1)
            self.assertEqual(result["agreement"]["conflict"], 1)
            self.assertEqual(result["agreement"]["agreement"], 0)

    def test_invalid_record_is_coverage_failure_not_normal_abstain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            citation = build_citation(
                _task(root / "task"),
                path="TASK.md",
                kind="task",
                start_line=1,
                end_line=1,
                claim="The task names the behavior.",
            )
            case_id = "fs__url_opener_core__hard3_001__test_invalid_path_control_characters"
            a = _write_run(
                root,
                reviewer="auditor_a",
                case_id=case_id,
                record=_record(
                    agent_id="auditor_a",
                    citation=citation,
                    task_id="fs__url_opener_core__hard3_001",
                    nodeid="evaluator_assertion::test_invalid_path_control_characters",
                ),
                valid=True,
            )
            b = _write_run(
                root,
                reviewer="auditor_b",
                case_id=case_id,
                record=None,
                valid=False,
                errors=["Agent did not create audit_record.json"],
            )
            result = aggregate_reviewer_runs(
                [("auditor_a", a), ("auditor_b", b)]
            )
            assertion = result["consensus"]["labels"][0]["assertions"][0]
            self.assertEqual(assertion["consensus_status"], "coverage_failure")
            self.assertEqual(assertion["label"], "unresolved")
            self.assertEqual(result["consensus"]["labels"][0]["task_primary"], "unresolved")
            self.assertEqual(result["agreement"]["coverage_failure"], 1)
            self.assertEqual(result["consensus"]["counts"]["abstain"], 0)
            self.assertEqual(result["consensus"]["counts"]["unresolved"], 1)


if __name__ == "__main__":
    unittest.main()
