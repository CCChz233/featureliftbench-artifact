from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "harness"))
sys.path.insert(0, str(_REPO_ROOT / "harness" / "scripts"))

import build_experiment_registry  # noqa: E402


class ExperimentRegistryTests(unittest.TestCase):
    def test_scope_recognizes_full_python150_main_suite(self) -> None:
        suite = Path(
            "experiments/python/openhands/model/compliant150-model-main-001"
        )

        self.assertEqual(build_experiment_registry._scope(suite, 150), "python150")

    def test_lifecycle_distinguishes_raw_leaderboard_from_support_copy(self) -> None:
        raw = Path("experiments/python/openhands/model/main-flash-20260705-232429")
        support = Path(
            "experiments/validation/v1_1/v1_1_infra_reevaluation/"
            "main-flash-20260705-232429"
        )
        superseded = Path(
            "experiments/python/openhands/model/batch3-flash-20260707-112646"
        )

        self.assertEqual(
            build_experiment_registry._lifecycle(raw, "main-flash-20260705-232429"),
            "frozen",
        )
        self.assertEqual(
            build_experiment_registry._lifecycle(support, "main-flash-20260705-232429"),
            "support",
        )
        self.assertEqual(
            build_experiment_registry._lifecycle(
                superseded, "batch3-flash-20260707-112646"
            ),
            "superseded",
        )

    def test_eval_score_is_canonical_but_run_status_stays_composite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp).resolve()
            suite_dir = repo_root / "experiments" / "python" / "openhands" / "model" / "run"
            task_dir = suite_dir / "task_a"
            (task_dir / "eval").mkdir(parents=True)
            (task_dir / "run.json").write_text(
                json.dumps(
                    {
                        "task_id": "task_a",
                        "status": "failed",
                        "evaluation": {"scores": {"final_score": 0.0}},
                    }
                ),
                encoding="utf-8",
            )
            (task_dir / "eval" / "result.json").write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "scores": {"final_score": 0.75},
                    }
                ),
                encoding="utf-8",
            )
            suite_path = suite_dir / "suite.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "total": 1,
                            "passed": 0,
                            "average_final_score": 0.0,
                        },
                        "runs": [
                            {
                                "task_id": "task_a",
                                "status": "failed",
                                "run_json": "/old/server/task_a/run.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(build_experiment_registry, "REPO_ROOT", repo_root):
                record, rows = build_experiment_registry.inspect_suite(suite_path)

            self.assertEqual(rows[0]["status"], "failed")
            self.assertEqual(rows[0]["final_score"], 0.75)
            self.assertEqual(record["passed"], 0)
            self.assertEqual(record["average_final_score"], 0.75)
            self.assertNotIn("summary_passed_mismatch", record["quality"]["flags"])
        self.assertIn("summary_average_mismatch", record["quality"]["flags"])

    def test_new_layout_categories_are_explicit(self) -> None:
        validation = Path("experiments/validation/batch3/run")
        method = Path("experiments/methods/ablation/run")
        self.assertEqual(build_experiment_registry._category(validation), "validation")
        self.assertEqual(build_experiment_registry._category(method), "method")

    def test_duplicate_run_ids_keep_all_raw_paths(self) -> None:
        duplicates = build_experiment_registry.duplicate_run_ids(
            [
                {"run_id": "same", "raw_path": "experiments/smoke/a"},
                {"run_id": "same", "raw_path": "experiments/smoke/b"},
                {"run_id": "unique", "raw_path": "experiments/smoke/c"},
            ]
        )
        self.assertEqual(
            duplicates,
            [
                {
                    "run_id": "same",
                    "raw_paths": ["experiments/smoke/a", "experiments/smoke/b"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
