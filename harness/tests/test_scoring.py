from __future__ import annotations

import unittest

from featureliftbench.scoring import clamp
from featureliftbench.scoring import functional_gate
from featureliftbench.scoring import score_submission


class ScoringTests(unittest.TestCase):
    def test_functional_gate(self) -> None:
        self.assertEqual(
            functional_gate(build_pass=True, test_pass=True, original_import_pass=True),
            1.0,
        )
        self.assertEqual(
            functional_gate(build_pass=True, test_pass=False, original_import_pass=True),
            0.0,
        )

    def test_explicit_functional_gates_fail_independently(self) -> None:
        passing = {
            "build_pass": True,
            "public_tests_pass": True,
            "hidden_tests_pass": True,
            "isolation_pass": True,
        }
        self.assertEqual(functional_gate(**passing), 1.0)
        for key in passing:
            case = dict(passing)
            case[key] = False
            with self.subTest(gate=key):
                self.assertEqual(functional_gate(**case), 0.0)

    def test_clamp(self) -> None:
        self.assertEqual(clamp(-1.0), 0.0)
        self.assertEqual(clamp(0.5), 0.5)
        self.assertEqual(clamp(2.0), 1.0)

    def test_score_submission_reports_reference_relative_compactness(self) -> None:
        scores = score_submission(
            metrics={
                "loc": 25,
                "source_loc": 1000,
                "reference_loc": 20,
            },
            metadata=_metadata(),
            functional_gate_score=1.0,
        )

        self.assertEqual(scores["extraction_ratio"], 1.25)
        self.assertEqual(scores["reference_relative_loc_ratio"], 1.25)
        self.assertEqual(scores["compactness_score"], 0.8)
        self.assertEqual(scores["final_score"], 1.0)

    def test_score_submission_does_not_mix_compactness_into_functional_score(self) -> None:
        scores = score_submission(
            metrics={
                "loc": 150,
                "source_loc": 100_000,
                "reference_loc": 100,
            },
            metadata=_metadata(),
            functional_gate_score=1.0,
        )

        self.assertEqual(scores["extraction_ratio"], 1.5)
        self.assertEqual(scores["compactness_score"], 0.666667)
        self.assertEqual(scores["final_score"], 1.0)

    def test_score_submission_keeps_compactness_independent_when_gate_fails(self) -> None:
        scores = score_submission(
            metrics={
                "loc": 25,
                "source_loc": 100,
                "reference_loc": 50,
            },
            metadata=_metadata(),
            functional_gate_score=0.0,
        )

        self.assertEqual(scores["extraction_ratio"], 0.5)
        self.assertEqual(scores["compactness_score"], 1.0)
        self.assertEqual(scores["final_score"], 0.0)

    def test_source_repository_loc_never_defines_v2_compactness(self) -> None:
        small_source = score_submission(
            metrics={"loc": 40, "source_loc": 100, "reference_loc": 20},
            metadata=_metadata(),
            functional_gate_score=1.0,
        )
        huge_source = score_submission(
            metrics={"loc": 40, "source_loc": 1_000_000, "reference_loc": 20},
            metadata=_metadata(),
            functional_gate_score=1.0,
        )

        self.assertEqual(small_source, huge_source)


def _metadata() -> dict:
    return {
        "scoring_reference": {
            "copy_all_bytes": 100,
            "copy_all_loc": 10,
            "oracle_bytes": 50,
            "oracle_loc": 5,
            "oracle_dependency_count": 0,
        }
    }


if __name__ == "__main__":
    unittest.main()
