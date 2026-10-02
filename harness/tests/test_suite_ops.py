from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "harness"))
sys.path.insert(0, str(_REPO_ROOT / "harness" / "scripts"))

import summarize_suite_infra  # noqa: E402
import validate_suite_resume  # noqa: E402
from analyze_benchmark_suite import aggregate_suite_summaries  # noqa: E402
from analyze_featurelift_suite import _output_paths  # noqa: E402
from analyze_suite_results import classify_runs  # noqa: E402
from analyze_suite_results import output_paths as suite_result_output_paths  # noqa: E402
from featureliftbench.suite_utils import compact_agent_usage  # noqa: E402
from featureliftbench.suite_utils import rebuild_suite_summary  # noqa: E402
from featureliftbench.suite_utils import resolve_suite_artifact_path  # noqa: E402


class PortableSuitePathTests(unittest.TestCase):
    def test_compact_usage_keeps_context_compression_audit(self) -> None:
        compact = compact_agent_usage(
            {
                "available": True,
                "total_tokens": 1000,
                "context_audit": {
                    "compression_mode": "token",
                    "condenser_trigger_tokens": 57344,
                    "condenser_target_tokens": 28672,
                    "condensation_events": 2,
                    "forgotten_event_count": 44,
                    "max_prompt_tokens_per_call": 57000,
                    "context_violation": False,
                },
            }
        )

        audit = compact["context_audit"]
        self.assertEqual(audit["compression_mode"], "token")
        self.assertEqual(audit["condensation_events"], 2)
        self.assertEqual(audit["forgotten_event_count"], 44)
        self.assertEqual(audit["condenser_trigger_tokens"], 57344)

    def test_task_local_artifact_wins_over_stale_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            local_run = suite_dir / "task_a" / "run.json"
            local_run.parent.mkdir(parents=True)
            local_run.write_text("{}", encoding="utf-8")

            resolved = resolve_suite_artifact_path(
                suite_dir,
                "task_a",
                "run.json",
                "/old/server/experiments/task_a/run.json",
            )

            self.assertEqual(resolved, local_run)

    def test_dotted_run_id_is_not_treated_as_a_suffix(self) -> None:
        prefix = Path("hard50-qwen3.6-27b-analysis")
        json_path, md_path = _output_paths(prefix)
        self.assertEqual(json_path.name, "hard50-qwen3.6-27b-analysis.json")
        self.assertEqual(md_path.name, "hard50-qwen3.6-27b-analysis.md")

        json_path, md_path = suite_result_output_paths(prefix)
        self.assertEqual(json_path.name, "hard50-qwen3.6-27b-analysis.json")
        self.assertEqual(md_path.name, "hard50-qwen3.6-27b-analysis.md")

    def test_suite_average_uses_all_assigned_tasks_as_denominator(self) -> None:
        summary = rebuild_suite_summary(
            [
                {
                    "task_id": "passed",
                    "status": "passed",
                    "agent": {"passed": True},
                    "submission": {"exists": True},
                    "evaluation": {"scores": {"final_score": 0.8}},
                },
                {
                    "task_id": "missing",
                    "status": "missing_submission",
                    "agent": {"passed": False},
                    "submission": {"exists": False},
                    "evaluation": {},
                },
            ]
        )

        self.assertEqual(summary["average_final_score"], 0.4)

    def test_functional_pass_is_independent_of_workflow_status(self) -> None:
        summary = rebuild_suite_summary(
            [
                {
                    "task_id": "recovered_after_agent_limit",
                    "status": "failed",
                    "agent": {"passed": False},
                    "submission": {"exists": True},
                    "evaluation": {
                        "scores": {"functional_gate": 1.0, "final_score": 1.0}
                    },
                },
                {
                    "task_id": "formal_failure",
                    "status": "failed",
                    "agent": {"passed": True},
                    "submission": {"exists": True},
                    "evaluation": {
                        "scores": {"functional_gate": 0.0, "final_score": 0.0}
                    },
                },
            ]
        )

        self.assertEqual(summary["passed"], 0)
        self.assertEqual(summary["run_status_passed"], 0)
        self.assertEqual(summary["functional_passed"], 1)
        self.assertEqual(summary["functional_failed"], 1)
        self.assertEqual(summary["functional_pass_rate"], 0.5)

    def test_aggregate_reports_formal_and_workflow_pass_rates_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            suite_dir.mkdir()
            (suite_dir / "suite.json").write_text(
                json.dumps(
                    {
                        "summary": {"total": 2, "passed": 0},
                        "runs": [
                            {"task_id": "a", "status": "failed", "final_score": 1.0},
                            {"task_id": "b", "status": "failed", "final_score": 0.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            aggregate = aggregate_suite_summaries([suite_dir])

        self.assertEqual(aggregate["passed"]["mean"], 0.0)
        self.assertEqual(aggregate["functional_passed"]["mean"], 1.0)
        self.assertEqual(aggregate["pass_rate"]["mean"], 0.0)
        self.assertEqual(aggregate["functional_pass_rate"]["mean"], 0.5)

    def test_result_classification_uses_functional_gate_not_agent_status(self) -> None:
        classifications = classify_runs(
            [
                {
                    "suite": "demo",
                    "task_id": "formal_pass",
                    "status": "failed",
                    "functional_gate": 1.0,
                    "extraction_ratio": 0.9,
                },
                {
                    "suite": "demo",
                    "task_id": "formal_fail",
                    "status": "passed",
                    "functional_gate": 0.0,
                    "extraction_ratio": 0.1,
                },
            ]
        )

        self.assertEqual(
            [row["task_id"] for row in classifications["failures"]],
            ["formal_fail"],
        )
        self.assertEqual(
            [row["task_id"] for row in classifications["high_extraction_ratio_passes"]],
            ["formal_pass"],
        )


class ValidateSuiteResumeTests(unittest.TestCase):
    def test_valid_suite_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            task_dir = suite_dir / "task_a"
            (task_dir / "submission").mkdir(parents=True)
            (task_dir / "agent").mkdir(parents=True)
            (task_dir / "eval").mkdir(parents=True)
            (task_dir / "run.json").write_text(
                json.dumps(
                    {
                        "task_id": "task_a",
                        "status": "passed",
                        "agent": {
                            "usage": {
                                "available": True,
                                "api_calls": 2,
                                "assistant_steps": 2,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (task_dir / "agent" / "usage.json").write_text(
                json.dumps({"api_calls": 2, "assistant_steps": 2}),
                encoding="utf-8",
            )
            (task_dir / "eval" / "result.json").write_text(
                json.dumps({"sandbox": {"backend": "docker"}}),
                encoding="utf-8",
            )
            (suite_dir / "suite.json").write_text(
                json.dumps({"runs": [{"task_id": "task_a", "status": "passed"}]}),
                encoding="utf-8",
            )

            errors = validate_suite_resume.validate_suite_resume(
                suite_dir,
                require_docker_eval=True,
            )
            self.assertEqual(errors, [])

    def test_zero_steps_with_api_calls_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            task_dir = suite_dir / "task_a"
            (task_dir / "submission").mkdir(parents=True)
            (task_dir / "agent").mkdir(parents=True)
            (task_dir / "run.json").write_text(
                json.dumps(
                    {
                        "task_id": "task_a",
                        "status": "passed",
                        "agent": {
                            "usage": {
                                "available": True,
                                "api_calls": 3,
                                "assistant_steps": 0,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (task_dir / "agent" / "usage.json").write_text(
                json.dumps({"api_calls": 3, "assistant_steps": 0}),
                encoding="utf-8",
            )
            (suite_dir / "suite.json").write_text(
                json.dumps({"runs": [{"task_id": "task_a", "status": "passed"}]}),
                encoding="utf-8",
            )

            errors = validate_suite_resume.validate_suite_resume(suite_dir)
            self.assertTrue(any("assistant_steps" in error for error in errors))


class SummarizeSuiteInfraTests(unittest.TestCase):
    def test_infra_clean_when_only_model_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            suite_dir.mkdir()
            (suite_dir / "suite.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "total": 2,
                            "passed": 1,
                            "failure_classes": {
                                "passed": 1,
                                "model_failed": 1,
                            },
                            "agent_failures": 0,
                            "docker_sandbox_failures": 0,
                            "log_limit_failures": 0,
                        },
                        "runs": [
                            {"task_id": "a", "status": "passed"},
                            {"task_id": "b", "status": "failed"},
                        ],
                        "agent_usage_totals": {"total_tokens": 100, "api_calls": 5},
                    }
                ),
                encoding="utf-8",
            )

            summary = summarize_suite_infra.summarize_suite_infra(suite_dir)
            self.assertTrue(summary["infra_clean"])
            self.assertEqual(summary["agent_usage_totals"]["total_tokens"], 100)

    def test_infra_not_clean_on_eval_infra_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            suite_dir.mkdir()
            (suite_dir / "suite.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "total": 1,
                            "passed": 0,
                            "failure_classes": {"eval_infra_failed": 1},
                            "docker_sandbox_failures": 1,
                        },
                        "runs": [{"task_id": "a", "status": "failed"}],
                    }
                ),
                encoding="utf-8",
            )

            summary = summarize_suite_infra.summarize_suite_infra(suite_dir)
            self.assertFalse(summary["infra_clean"])
            self.assertEqual(summary["infra_failure_classes"], {"eval_infra_failed": 1})


if __name__ == "__main__":
    unittest.main()
