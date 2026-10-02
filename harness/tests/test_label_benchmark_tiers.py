"""Protocol v2 labeler: three-state aggregation and fail-closed publishing."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

import label_benchmark_tiers as lbl  # noqa: E402


class AggregateLabelTests(unittest.TestCase):
    def test_confirmed_fail_beats_undetermined(self) -> None:
        self.assertEqual(
            lbl.aggregate_label(
                [
                    lbl.check(
                        "R-PACKAGE",
                        status="undetermined",
                        mechanical_result="error",
                        adjudication="pending",
                        evidence=[],
                        input_sha256="a",
                    ),
                    lbl.check(
                        "R-ORACLE",
                        status="fail",
                        mechanical_result="hit",
                        adjudication="not_needed",
                        evidence=[],
                        input_sha256="b",
                    ),
                ]
            ),
            lbl.VIOLATES,
        )

    def test_any_undetermined_blocks_meets(self) -> None:
        self.assertEqual(
            lbl.aggregate_label(
                [
                    lbl.check(
                        "R-PACKAGE",
                        status="pass",
                        mechanical_result="clear",
                        adjudication="not_needed",
                        evidence=[],
                        input_sha256="a",
                    ),
                    lbl.check(
                        "R-SURFACE",
                        status="undetermined",
                        mechanical_result="hit",
                        adjudication="pending",
                        evidence=["Cache.__getitem__"],
                        input_sha256="b",
                    ),
                ]
            ),
            lbl.UNDETERMINED,
        )

    def test_all_pass_is_meets(self) -> None:
        self.assertEqual(
            lbl.aggregate_label(
                [
                    lbl.check(
                        rule,
                        status="pass",
                        mechanical_result="clear",
                        adjudication="not_needed",
                        evidence=[],
                        input_sha256="x",
                    )
                    for rule in ("R-PACKAGE", "R-ORACLE", "R-SURFACE", "R-ENTRY")
                ]
            ),
            lbl.MEETS,
        )


class AdjudicationTests(unittest.TestCase):
    def test_c1_hit_is_pending_until_adjudicated(self) -> None:
        status, adjudication = lbl.apply_adjudication("hit", None)
        self.assertEqual(status, "undetermined")
        self.assertEqual(adjudication, "pending")

    def test_dangling_error_is_pending(self) -> None:
        status, adjudication = lbl.apply_adjudication("error", None)
        self.assertEqual(status, "undetermined")
        self.assertEqual(adjudication, "pending")

    def test_confirmed_violation_is_fail(self) -> None:
        status, adjudication = lbl.apply_adjudication("hit", "confirmed_violation")
        self.assertEqual(status, "fail")
        self.assertEqual(adjudication, "confirmed_violation")

    def test_false_positive_is_pass(self) -> None:
        status, adjudication = lbl.apply_adjudication("hit", "false_positive")
        self.assertEqual(status, "pass")
        self.assertEqual(adjudication, "false_positive")

    def test_insufficient_evidence_stays_undetermined(self) -> None:
        status, adjudication = lbl.apply_adjudication("hit", "insufficient_evidence")
        self.assertEqual(status, "undetermined")
        self.assertEqual(adjudication, "insufficient_evidence")


class FailClosedTests(unittest.TestCase):
    def test_missing_valid_field_is_not_pass(self) -> None:
        self.assertIsNone(lbl._explicit_bool({}, "valid"))
        self.assertIsNone(lbl._explicit_bool({"valid": "yes"}, "valid"))
        self.assertIs(lbl._explicit_bool({"valid": True}, "valid"), True)
        self.assertIs(lbl._explicit_bool({"valid": False}, "valid"), False)

    def test_write_selection_refuses_undetermined(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            lbl.write_selection(
                [
                    {
                        "task_id": "example__task__001",
                        "label": lbl.UNDETERMINED,
                        "checks": [],
                    }
                ],
                {},
            )
        self.assertIn("undetermined", str(caught.exception))

    def test_write_selection_is_opt_in(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--write-selection", action="store_true")
        args = parser.parse_args([])
        self.assertFalse(args.write_selection)

    def test_default_output_is_v2_candidate_not_v1(self) -> None:
        self.assertEqual(lbl.DEFAULT_OUTPUT.name, "benchmark_tiers_v2_candidate")
        self.assertEqual(lbl.V1_OUTPUT.name, "benchmark_tiers")
        self.assertNotEqual(lbl.DEFAULT_OUTPUT, lbl.V1_OUTPUT)


class SurfaceMechanicalTests(unittest.TestCase):
    def test_graphene_class_body_is_not_a_c1_hit(self) -> None:
        task = (
            _REPO
            / "benchmark"
            / "python200_hard_tasks"
            / "graphene__schema_execute_core__001"
        )
        mechanical, members = lbl.undeclared_surface(task)
        self.assertEqual(mechanical, "clear")
        self.assertEqual(members, [])

    def test_cache_subscript_is_a_c1_hit_not_an_implicit_pass(self) -> None:
        task = (
            _REPO
            / "benchmark"
            / "python200_hard_tasks"
            / "cachetools__cache_eviction_core__001"
        )
        mechanical, members = lbl.undeclared_surface(task)
        self.assertEqual(mechanical, "hit")
        self.assertTrue(
            any(item.endswith(".__getitem__") for item in members),
            members,
        )
        status, adjudication = lbl.apply_adjudication(mechanical, None)
        self.assertEqual(status, "undetermined")
        self.assertEqual(adjudication, "pending")


if __name__ == "__main__":
    unittest.main()
