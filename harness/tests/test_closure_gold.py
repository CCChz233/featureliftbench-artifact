from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.closure_gold import COMPLETE
from featureliftbench.closure_gold import LEGACY
from featureliftbench.closure_gold import load_closure_gold
from featureliftbench.closure_gold import score_closure


class ClosureGoldTests(unittest.TestCase):
    def test_legacy_loader_supports_both_manifest_fields_and_normalizes_repo_path(self) -> None:
        for field in ("required_source_files", "source_files"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                task = Path(tmp) / "sample"
                (task / "evaluation").mkdir(parents=True)
                (task / "repo" / "pkg").mkdir(parents=True)
                (task / "repo" / "pkg" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
                (task / "evaluation" / "oracle_manifest.json").write_text(
                    json.dumps({field: ["pkg/core.py"]}), encoding="utf-8"
                )

                gold = load_closure_gold(task)

                self.assertEqual(gold.completeness_for("file"), LEGACY)
                self.assertEqual(gold.approved_artifact_values(), {"repo/pkg/core.py"})
                self.assertIsNone(score_closure(gold, {"repo/pkg/core.py"}))

    def test_replaceable_requirement_counts_once_for_each_approved_solution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = self._write_replaceable_gold(Path(tmp))
            gold = load_closure_gold(task)

            original = score_closure(gold, {"pkg:original"}, kind="symbol")
            adapter = score_closure(gold, {"featurelifted.adapter:replacement"}, kind="symbol")
            rewritten = score_closure(gold, {"featurelifted.core:replacement"}, kind="symbol")

            for score in (original, adapter, rewritten):
                assert score is not None
                self.assertEqual(score.required_requirement_count, 1)
                self.assertEqual(score.satisfied_requirement_count, 1)
                self.assertEqual(score.recall, 1.0)

    def test_multiple_replaceable_solutions_do_not_inflate_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = self._write_replaceable_gold(Path(tmp))
            score = score_closure(
                load_closure_gold(task),
                {"pkg:original", "featurelifted.adapter:replacement", "featurelifted.core:replacement"},
                kind="symbol",
            )

            assert score is not None
            self.assertEqual(score.required_requirement_count, 1)
            self.assertEqual(score.satisfied_requirement_count, 1)
            self.assertEqual(score.recall, 1.0)
            self.assertEqual(score.redundant_alternative_count, 2)

    def test_optional_requirement_is_not_in_recall_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = self._write_replaceable_gold(Path(tmp), include_optional=True)
            score = score_closure(load_closure_gold(task), {"pkg:original"}, kind="symbol")

            assert score is not None
            self.assertEqual(score.required_requirement_count, 1)
            self.assertEqual(score.recall, 1.0)

    def test_missing_required_requirement_has_zero_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = self._write_replaceable_gold(Path(tmp))
            score = score_closure(load_closure_gold(task), set(), kind="symbol")

            assert score is not None
            self.assertEqual(score.recall, 0.0)

    def _write_replaceable_gold(self, root: Path, *, include_optional: bool = False) -> Path:
        task = root / "sample"
        (task / "evaluation").mkdir(parents=True)
        requirements = [
            {
                "requirement_id": "validation_contract",
                "kind": "symbol",
                "necessity": "must",
                "satisfied_by": [
                    {"solution_id": "original", "artifacts": [{"module": "pkg", "symbol": "original"}]},
                    {
                        "solution_id": "adapter",
                        "artifacts": [{"module": "featurelifted.adapter", "symbol": "replacement"}],
                    },
                    {
                        "solution_id": "rewrite",
                        "artifacts": [{"module": "featurelifted.core", "symbol": "replacement"}],
                    },
                ],
            }
        ]
        if include_optional:
            requirements.append(
                {
                    "requirement_id": "optional_helper",
                    "kind": "symbol",
                    "necessity": "optional",
                    "satisfied_by": [
                        {"solution_id": "helper", "artifacts": [{"module": "pkg", "symbol": "helper"}]}
                    ],
                }
            )
        payload = {
            "schema_version": "featureliftbench.closure_gold.v1",
            "task_id": "sample",
            "closure_variants": [{"variant_id": "default", "requirements": requirements}],
            "gold_completeness": {"symbol": COMPLETE},
            "review": {"status": "double_reviewed"},
        }
        (task / "evaluation" / "closure_gold.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return task


if __name__ == "__main__":
    unittest.main()
