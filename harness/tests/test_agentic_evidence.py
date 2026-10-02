from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.agentic_evidence import AUDIT_RECORD_SCHEMA
from featureliftbench.agentic_evidence import EVIDENCE_PACK_SCHEMA
from featureliftbench.agentic_evidence import adjudicate_records
from featureliftbench.agentic_evidence import build_citation
from featureliftbench.agentic_evidence import clamp_line_range
from featureliftbench.agentic_evidence import coerce_confidence
from featureliftbench.agentic_evidence import generate_canary_suite
from featureliftbench.agentic_evidence import validate_audit_record
from featureliftbench.agentic_evidence import validate_citation
from featureliftbench.agentic_evidence import validate_evidence_pack
from featureliftbench.agentic_evidence.canaries import validate_canary_suite
from featureliftbench.agentic_evidence.canaries import _EXAMPLES
from featureliftbench.agentic_evidence.calibration import load_record_directory
from featureliftbench.agentic_evidence.calibration import score_canary_records
from featureliftbench.agentic_evidence.prompts import AUDITOR_FINAL_PROMPT
from featureliftbench.agentic_evidence.prompts import auditor_prompt
from featureliftbench.agentic_evidence.direct_auditor import finalize_proposed_record
from featureliftbench.agentic_evidence.direct_auditor import parse_json_response
from featureliftbench.agentic_evidence.direct_auditor import render_case_prompt


def _task(root: Path) -> Path:
    task = root / "demo"
    (task / "repo" / "pkg").mkdir(parents=True)
    (task / "TASK.md").write_text(
        "# Demo\n\nNormalize text according to the repository.\n",
        encoding="utf-8",
    )
    (task / "metadata.json").write_text(
        json.dumps(
            {
                "public_spec": {
                    "behaviors": [{"id": "B001", "text": "Normalize text."}]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (task / "repo" / "pkg" / "normalize.py").write_text(
        "import unicodedata\n\n"
        "def normalize(value: str) -> str:\n"
        "    return unicodedata.normalize('NFKC', value).casefold()\n",
        encoding="utf-8",
    )
    return task


def _audit(agent_id: str, citation: dict, *, verdict: str = "recoverable") -> dict:
    return {
        "schema_version": AUDIT_RECORD_SCHEMA,
        "task_id": "demo",
        "nodeid": "private_evaluator/test_x.py::test_x",
        "agent_id": agent_id,
        "verdict": verdict,
        "confidence": 0.9,
        "public_obligation_ids": ["B001"],
        "evidence": [citation] if verdict != "underdetermined" else [],
        "counterevidence": [],
        "abstain_reason": "",
    }


class AgenticEvidenceTests(unittest.TestCase):
    def test_citation_round_trip_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _task(Path(tmp))
            citation = build_citation(
                task,
                path="repo/pkg/normalize.py",
                kind="repository",
                start_line=3,
                end_line=4,
                claim="The canonical implementation applies NFKC and casefold.",
            )
            self.assertEqual(validate_citation(task, citation), [])
            citation["sha256"] = "0" * 64
            self.assertIn("digest mismatch", "\n".join(validate_citation(task, citation)))

    def test_citation_rejects_private_and_traversal_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _task(Path(tmp))
            base = {
                "kind": "repository",
                "start_line": 1,
                "end_line": 1,
                "sha256": "0" * 64,
                "claim": "claim",
            }
            private = dict(base, path="hidden_tests/test_x.py")
            traversal = dict(base, path="repo/../../hidden_tests/test_x.py")
            self.assertIn("repo/", "\n".join(validate_citation(task, private)))
            self.assertIn("traversal", "\n".join(validate_citation(task, traversal)))

    def test_audit_schema_requires_evidence_for_recoverable(self) -> None:
        record = {
            "schema_version": AUDIT_RECORD_SCHEMA,
            "task_id": "demo",
            "nodeid": "test_x",
            "agent_id": "agent-a",
            "verdict": "recoverable",
            "confidence": 0.9,
            "public_obligation_ids": [],
            "evidence": [],
            "counterevidence": [],
        }
        self.assertIn(
            "requires at least one evidence citation",
            "\n".join(validate_audit_record(record)),
        )

    def test_consensus_requires_shared_reproducible_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _task(Path(tmp))
            citation = build_citation(
                task,
                path="repo/pkg/normalize.py",
                kind="repository",
                start_line=3,
                end_line=4,
                claim="The implementation applies NFKC and casefold.",
            )
            result = adjudicate_records(
                [_audit("agent-a", citation), _audit("agent-b", citation)]
            )
            self.assertEqual(result["verdict"], "recoverable")
            self.assertEqual(result["votes"], 2)
            other = build_citation(
                task,
                path="TASK.md",
                kind="task",
                start_line=1,
                end_line=1,
                claim="The task identifies the target feature.",
            )
            result = adjudicate_records(
                [_audit("agent-a", citation), _audit("agent-b", other)]
            )
            self.assertEqual(result["verdict"], "abstain")
            self.assertIn("share", result["abstain_reason"])

    def test_consensus_abstains_on_two_agent_label_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _task(Path(tmp))
            citation = build_citation(
                task,
                path="repo/pkg/normalize.py",
                kind="repository",
                start_line=3,
                end_line=4,
                claim="The implementation applies NFKC and casefold.",
            )

            result = adjudicate_records(
                [
                    _audit("agent-a", citation, verdict="explicit"),
                    _audit("agent-b", citation, verdict="underdetermined"),
                ]
            )

            self.assertEqual(result["verdict"], "abstain")
            self.assertIn("no verdict reached 2 votes", result["abstain_reason"])

    def test_evidence_pack_firewall_blocks_hidden_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _task(Path(tmp))
            citation = build_citation(
                task,
                path="repo/pkg/normalize.py",
                kind="repository",
                start_line=3,
                end_line=4,
                claim="The implementation applies NFKC and casefold.",
            )
            pack = {
                "schema_version": EVIDENCE_PACK_SCHEMA,
                "task_id": "demo",
                "generator_id": "miner-a",
                "information_boundary": "task_public_spec_repo_only",
                "entries": [
                    {
                        "title": "B001 normalization",
                        "citations": [citation],
                    }
                ],
            }
            self.assertEqual(validate_evidence_pack(pack, task), [])
            pack["hidden_nodeid"] = "hidden_tests/test_x.py::test_x"
            errors = validate_evidence_pack(pack, task)
            self.assertIn("forbidden audit-only key", "\n".join(errors))
            self.assertIn("forbidden Hidden/evaluator reference", "\n".join(errors))

    def test_generates_balanced_opaque_canary_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "canaries"
            manifest = generate_canary_suite(root, per_class=2, seed=7)
            self.assertEqual(manifest["case_count"], 8)
            self.assertEqual(validate_canary_suite(root), [])
            counts: dict[str, int] = {}
            for row in manifest["cases"]:
                verdict = row["expected_verdict"]
                counts[verdict] = counts.get(verdict, 0) + 1
                case_dir = root / "cases" / row["case_id"]
                public = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in case_dir.rglob("*")
                    if path.is_file()
                )
                self.assertNotIn("expected_verdict", public)
                self.assertNotIn(verdict, row["case_id"])
            self.assertEqual(set(counts.values()), {2})
            ambiguous_id = next(
                row["case_id"]
                for row in manifest["cases"]
                if row["expected_verdict"] == "ambiguous"
            )
            ambiguous_unicode = (
                root / "cases" / ambiguous_id / "repo/textcore/unicode.py"
            ).read_text(encoding="utf-8")
            self.assertIn("Supported Unicode", ambiguous_unicode)
            self.assertNotIn("Canonical normalization", ambiguous_unicode)

    def test_scores_canaries_without_exposing_manifest_to_prompt(self) -> None:
        manifest = {
            "cases": [
                {"case_id": "a", "expected_verdict": "explicit"},
                {"case_id": "b", "expected_verdict": "recoverable"},
                {"case_id": "c", "expected_verdict": "ambiguous"},
                {"case_id": "d", "expected_verdict": "underdetermined"},
            ]
        }
        records = {
            case_id: {"verdict": verdict}
            for case_id, verdict in (
                ("a", "explicit"),
                ("b", "recoverable"),
                ("c", "ambiguous"),
                ("d", "underdetermined"),
            )
        }
        result = score_canary_records(manifest, records)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["macro_f1"], 1.0)
        prompt = auditor_prompt(agent_id="auditor-a")
        self.assertNotIn("private_manifest.json", prompt)
        self.assertNotIn("expected_verdict", prompt)
        self.assertIn('"agent_id": "auditor-a"', prompt)
        self.assertIn("record = {\n", prompt)
        self.assertIn('json.dumps(record, indent=2) + "\\n"', prompt)
        self.assertIn("Use at most 24 shell/tool actions", prompt)
        self.assertIn("A valid record is terminal", prompt)
        self.assertIn("exactly one model response", AUDITOR_FINAL_PROMPT)
        self.assertIn("audit_record.json", AUDITOR_FINAL_PROMPT)
        self.assertIn("complete conservative record", AUDITOR_FINAL_PROMPT)

    def test_record_loader_excludes_unvalidated_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for case_id, valid in (("valid-case", True), ("invalid-case", False)):
                case = root / case_id
                case.mkdir()
                (case / "audit_record.json").write_text(
                    json.dumps({"verdict": "explicit"}) + "\n",
                    encoding="utf-8",
                )
                (case / "validation.json").write_text(
                    json.dumps({"valid": valid}) + "\n",
                    encoding="utf-8",
                )
            missing_validation = root / "missing-validation"
            missing_validation.mkdir()
            (missing_validation / "audit_record.json").write_text(
                json.dumps({"verdict": "explicit"}) + "\n",
                encoding="utf-8",
            )

            records = load_record_directory(root)

            self.assertEqual(set(records), {"valid-case"})

    def test_direct_auditor_finalizes_model_citation_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _task(Path(tmp))
            proposal = parse_json_response(
                "```json\n"
                + json.dumps(
                    {
                        "task_id": "demo",
                        "nodeid": "private_evaluator/test_x.py::test_x",
                        "verdict": "recoverable",
                        "confidence": 0.92,
                        "public_obligation_ids": ["B001"],
                        "evidence": [
                            {
                                "path": "repo/pkg/normalize.py",
                                "kind": "source",
                                "start_line": 3,
                                "end_line": 4,
                                "claim": "The unique implementation uses casefold.",
                            }
                        ],
                        "counterevidence": [],
                        "abstain_reason": "",
                    }
                )
                + "\n```"
            )
            record = finalize_proposed_record(
                proposal, task_dir=task, agent_id="direct-a"
            )
            self.assertEqual(validate_audit_record(record), [])
            self.assertEqual(validate_citation(task, record["evidence"][0]), [])
            self.assertEqual(len(record["evidence"][0]["sha256"]), 64)
            self.assertEqual(record["evidence"][0]["kind"], "repository")

    def test_direct_prompt_contains_only_case_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "canaries"
            manifest = generate_canary_suite(root, per_class=1, seed=11)
            case_id = manifest["cases"][0]["case_id"]
            prompt = render_case_prompt(root / "cases" / case_id, agent_id="a")
            self.assertIn("===== TASK.md =====", prompt)
            self.assertIn("===== audit_packet.json =====", prompt)
            self.assertNotIn("private_manifest", prompt)
            self.assertNotIn("expected_verdict", prompt)

    def test_canary_examples_discriminate_legacy_and_unicode_semantics(self) -> None:
        import unicodedata

        for source, expected in _EXAMPLES:
            self.assertEqual(unicodedata.normalize("NFKC", source).casefold(), expected)
            self.assertNotEqual(source.lower(), expected)

    def test_clamp_line_range_repairs_overshoot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("a\nb\nc\n", encoding="utf-8")
            self.assertEqual(clamp_line_range(path, 1, 5), (1, 3))
            self.assertEqual(clamp_line_range(path, 4, 6), (3, 3))
            task = _task(Path(tmp) / "task_root")
            citation = build_citation(
                task,
                path="repo/pkg/normalize.py",
                kind="repository",
                start_line=1,
                end_line=99,
                claim="clamped repository excerpt",
            )
            line_count = len(
                (task / "repo/pkg/normalize.py").read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(citation["end_line"], line_count)
            self.assertEqual(validate_citation(task, citation), [])

    def test_coerce_confidence_accepts_strings_and_percentages(self) -> None:
        self.assertEqual(coerce_confidence(0.9), 0.9)
        self.assertEqual(coerce_confidence("0.75"), 0.75)
        self.assertEqual(coerce_confidence("80%"), 0.8)
        self.assertEqual(coerce_confidence("high"), 0.5)
        self.assertEqual(coerce_confidence(True), 0.5)
        with tempfile.TemporaryDirectory() as tmp:
            record = finalize_proposed_record(
                {
                    "task_id": "demo",
                    "nodeid": "t",
                    "verdict": "underdetermined",
                    "confidence": "medium",
                    "public_obligation_ids": [],
                    "evidence": [],
                    "counterevidence": [],
                    "abstain_reason": "",
                },
                task_dir=_task(Path(tmp)),
                agent_id="a",
            )
            self.assertEqual(record["confidence"], 0.5)
            self.assertEqual(validate_audit_record(record), [])


if __name__ == "__main__":
    unittest.main()
