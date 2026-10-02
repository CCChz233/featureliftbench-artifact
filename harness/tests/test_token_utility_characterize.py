from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.token_utility_axes import cohort_of, load_lift_types, load_task_axes, model_label

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "harness/scripts/analyze_token_utility_characterize.py"
SPEC = importlib.util.spec_from_file_location("analyze_token_utility_characterize", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class AxisTests(unittest.TestCase):
    def test_hard3_and_external50_cohorts(self) -> None:
        self.assertEqual(cohort_of("glom__spec_eval_core__hard3_001"), "hard3")
        self.assertEqual(
            cohort_of("toolz__compose_pipe_core__001", ["external50", "direct"]),
            "external50",
        )
        self.assertEqual(cohort_of("arrow__parse_format_core__001", ["batch-1"]), "python150")

    def test_model_labels_stay_stratified(self) -> None:
        self.assertEqual(
            model_label("/x/python200-deepseek-v4-flash-vllm-local-0812-001"),
            "flash_local_main200",
        )
        self.assertEqual(
            model_label("/x/external50-gpt-oss-120b-0817-main-001"),
            "oss120b_e50",
        )
        self.assertNotEqual(
            model_label("/x/external50-qwen3.6-35b-a3b-fp8-0817-main-001"),
            model_label("/x/python200-deepseek-v4-flash-vllm-local-0812-001"),
        )

    def test_load_lift_types_prefers_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "expansion.json",
                {
                    "rows": [
                        {
                            "task_id": "a__001",
                            "disposition": "selected",
                            "final_lift_type": "Composite",
                        }
                    ]
                },
            )
            _write(
                root / "audit.json",
                {"tasks": [{"task_id": "a__001", "lift_type": "Direct"}]},
            )
            lifts = load_lift_types(
                audit_path=root / "audit.json",
                expansion_path=root / "expansion.json",
            )
            self.assertEqual(lifts["a__001"], "Direct")

    def test_axes_do_not_treat_metadata_difficulty_as_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "arrow__parse_format_core__001"
            _write(
                task / "metadata.json",
                {
                    "difficulty": "hard",
                    "tags": ["batch-1"],
                    "entanglement": {"level": "high"},
                },
            )
            axes = load_task_axes(
                "arrow__parse_format_core__001",
                tasks_root=Path(tmp),
                lift_types={"arrow__parse_format_core__001": "Adapted"},
            )
            self.assertEqual(axes["cohort"], "python150")
            self.assertEqual(axes["metadata_difficulty"], "hard")
            self.assertEqual(axes["lift_type"], "Adapted")
            self.assertNotEqual(axes["cohort"], axes["metadata_difficulty"])


class CharacterizeTests(unittest.TestCase):
    def test_tstar_frac_and_tail(self) -> None:
        row = MOD.gold_row(
            "/suite/python200-deepseek-v4-flash-vllm-local-0812-001",
            {"task_id": "demo__001"},
            {"earliest_pass_tokens": 400, "total_tokens": 1000},
            axes={
                "lift_type": "Direct",
                "cohort": "python150",
                "entanglement_level": "high",
            },
            post={"tail": 600, "tok": {"self_test_run": 300, "self_test_write": 60}},
        )
        self.assertEqual(row["tstar_frac"], 0.4)
        self.assertEqual(row["tail_tokens"], 600)
        self.assertEqual(row["verification_share"], 0.6)
        self.assertFalse(row["late_pass"])

    def test_summary_median(self) -> None:
        rows = [
            {
                "tstar_frac": 0.2,
                "t_star": 100,
                "total_tokens": 500,
                "tail_tokens": 400,
                "tail_frac": 0.8,
                "verification_share": 0.5,
                "late_pass": False,
            },
            {
                "tstar_frac": 0.4,
                "t_star": 200,
                "total_tokens": 500,
                "tail_tokens": 300,
                "tail_frac": 0.6,
                "verification_share": 0.4,
                "late_pass": False,
            },
            {
                "tstar_frac": 0.6,
                "t_star": 300,
                "total_tokens": 500,
                "tail_tokens": 200,
                "tail_frac": 0.4,
                "verification_share": 0.3,
                "late_pass": True,
            },
        ]
        out = MOD.summarize(rows, label="demo")
        self.assertEqual(out["n"], 3)
        self.assertAlmostEqual(out["tstar_frac_median"] or 0, 0.4)
        self.assertEqual(out["late_pass_n"], 1)


if __name__ == "__main__":
    unittest.main()
