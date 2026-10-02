from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from featureliftbench.repo_graph import pilot as pilot_module
from featureliftbench.repo_graph.pilot import PilotCell
from featureliftbench.repo_graph.pilot import analyze_pilot_results
from featureliftbench.repo_graph.pilot import build_execution_order
from featureliftbench.repo_graph.pilot import classify_controller_attempt
from featureliftbench.repo_graph.pilot import load_pilot_spec
from featureliftbench.repo_graph.pilot import run_pilot
from featureliftbench.repo_graph.pilot import stopping_reason
from featureliftbench.repo_graph.pilot import validate_arm_profiles


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "harness/config/experiments/rsg_openhands_pilot_v1.toml"


class RepoGraphPilotTests(unittest.TestCase):
    def test_frozen_order_has_paid_pair_then_twelve_unique_cells(self) -> None:
        spec = load_pilot_spec(SPEC)
        cells = build_execution_order(spec)
        self.assertEqual(len(cells), 12)
        self.assertEqual(len({cell.cell_id for cell in cells}), 12)
        self.assertEqual((cells[0].task_id, cells[0].arm), (spec["tasks"][0], "p0"))
        self.assertEqual((cells[1].task_id, cells[1].arm), (spec["tasks"][0], "p3"))
        self.assertEqual(
            [cell.cell_id for cell in cells],
            [cell.cell_id for cell in build_execution_order(spec)],
        )

    def test_profiles_are_identical_outside_rsg_and_freeze_context(self) -> None:
        spec = load_pilot_spec(SPEC)
        result = validate_arm_profiles(spec, root=ROOT)
        self.assertEqual(result["summaries"]["p0"]["repo_graph_mode"], "disabled")
        self.assertEqual(result["summaries"]["p3"]["repo_graph_mode"], "closure")
        self.assertEqual(
            result["summaries"]["p3"]["openhands_condenser_trigger_tokens"],
            122880,
        )

    def test_paid_pair_and_four_run_adoption_stops(self) -> None:
        spec = load_pilot_spec(SPEC)
        paid_pair_state = {
            "results": [
                {"arm": "p0", "infrastructure_failure": False, "context_violation": False},
                {
                    "arm": "p3",
                    "infrastructure_failure": False,
                    "context_violation": False,
                    "graph_initialized": True,
                    "graph_leakage": False,
                    "protocol_violation": False,
                    "adoption_compliant": False,
                },
            ],
            "consecutive_infrastructure_failures": 0,
            "observed_total_tokens": 1,
        }
        self.assertEqual(
            stopping_reason(spec, paid_pair_state),
            "paid_pair_rsg_adoption_gate_failed",
        )
        results = [
            {
                "arm": "p3",
                "graph_initialized": True,
                "graph_leakage": False,
                "protocol_violation": False,
                "context_violation": False,
                "adoption_compliant": index < 2,
            }
            for index in range(4)
        ]
        self.assertEqual(
            stopping_reason(
                spec,
                {
                    "results": results,
                    "consecutive_infrastructure_failures": 0,
                    "observed_total_tokens": 1,
                },
            ),
            "rsg_adoption_below_75_percent",
        )

    def test_nonzero_cli_exit_does_not_retry_a_structured_model_failure(self) -> None:
        attempt = classify_controller_attempt(
            1,
            {
                "status": "failed",
                "agent": {"passed": True, "reason": "", "usage": {"api_calls": 1}},
                "submission": {"exists": True},
                "evaluation": {"status": "failed"},
            },
        )
        self.assertTrue(attempt["cli_nonzero"])
        self.assertEqual(attempt["failure_class"], "model_failed")
        self.assertFalse(attempt["infrastructure_failure"])

    def test_missing_run_is_retryable_even_with_zero_cli_exit(self) -> None:
        attempt = classify_controller_attempt(0, {})
        self.assertEqual(attempt["failure_class"], "missing_run")
        self.assertTrue(attempt["infrastructure_failure"])

    def test_retries_use_isolated_attempt_directories(self) -> None:
        spec = load_pilot_spec(SPEC)
        cell = PilotCell(
            order=1,
            task_id=spec["tasks"][0],
            arm="p0",
            replicate=1,
            profile=spec["arms"]["p0"]["profile"],
        )
        infrastructure_run = {
            "status": "failed",
            "agent": {"passed": False, "usage": {"available": True, "api_calls": 0}},
            "submission": {"exists": False},
            "evaluation": {"status": "not-run"},
        }
        logical_run = {
            "status": "failed",
            "agent": {"passed": True, "usage": {"api_calls": 1}},
            "submission": {"exists": True},
            "evaluation": {"status": "failed"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            experiment_dir = Path(tmp)
            with (
                patch.object(pilot_module, "build_execution_order", return_value=[cell]),
                patch.object(pilot_module, "pilot_cell_command", return_value=["noop"]),
                patch.object(
                    pilot_module.subprocess,
                    "run",
                    side_effect=[SimpleNamespace(returncode=1), SimpleNamespace(returncode=1)],
                ),
                patch.object(
                    pilot_module,
                    "load_cell_result",
                    side_effect=[infrastructure_run, logical_run],
                ) as load_result,
                patch.object(
                    pilot_module,
                    "cell_result_record",
                    return_value={
                        **cell.to_dict(),
                        "infrastructure_failure": False,
                        "context_violation": False,
                        "total_tokens": 10,
                        "formal_pass": False,
                        "adoption_compliant": False,
                    },
                ),
            ):
                state = run_pilot(spec, experiment_dir=experiment_dir, root=ROOT, execute=True)

            attempt_1 = experiment_dir / "cells" / cell.cell_id / "attempts" / "attempt_01"
            attempt_2 = experiment_dir / "cells" / cell.cell_id / "attempts" / "attempt_02"
            self.assertEqual(
                load_result.call_args_list,
                [call(attempt_1, cell.task_id), call(attempt_2, cell.task_id)],
            )
            self.assertEqual(state["status"], "complete")
            attempts = (
                experiment_dir / "cells" / cell.cell_id / "controller_attempts.json"
            ).read_text(encoding="utf-8")
            self.assertIn(str(attempt_1), attempts)
            self.assertIn(str(attempt_2), attempts)

    def test_synthetic_twelve_runs_pair_without_significance_claim(self) -> None:
        spec = load_pilot_spec(SPEC)
        rows = []
        for cell in build_execution_order(spec):
            rows.append(
                {
                    **cell.to_dict(),
                    "formal_pass": cell.arm == "p3",
                    "total_tokens": 1000 + cell.order,
                    "adoption_compliant": cell.arm == "p3",
                }
            )
        analysis = analyze_pilot_results(rows)
        self.assertEqual(len(analysis["paired_differences"]), 6)
        self.assertEqual(
            analysis["reporting_scope"],
            "descriptive_only_no_significance_or_causal_claim",
        )
        self.assertEqual(analysis["by_arm"]["p3"]["adoption_compliant_runs"], 6)


if __name__ == "__main__":
    unittest.main()
