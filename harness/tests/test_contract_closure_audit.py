from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.contract_closure_audit import (
    REVIEW_SCHEMA,
    _assertions,
    _test_functions,
    validate_review,
)


class ContractClosureAuditTests(unittest.TestCase):
    def test_extracts_functions_assertions_and_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            tests = task / "hidden_tests"
            tests.mkdir()
            (tests / "test_behavior.py").write_text(
                "import pytest\n\n"
                "def test_value():\n"
                "    assert 1 + 1 == 2\n\n"
                "class TestErrors:\n"
                "    def test_bad(self):\n"
                "        with pytest.raises(ValueError, match='bad'):\n"
                "            raise ValueError('bad')\n",
                encoding="utf-8",
            )
            functions = _test_functions(task, "hidden_tests")
            self.assertEqual(
                [item.nodeid for item in functions],
                [
                    "hidden_tests/test_behavior.py::test_value",
                    "hidden_tests/test_behavior.py::TestErrors::test_bad",
                ],
            )
            first = _assertions(functions[0].source, start_line=functions[0].line)
            second = _assertions(functions[1].source, start_line=functions[1].line)
            self.assertEqual(first[0]["kind"], "assert")
            self.assertEqual(second[0]["kind"], "raises")

    def test_review_requires_every_test_and_evidence(self) -> None:
        task = {"task_id": "demo", "tests": [{"nodeid": "hidden_tests/test_x.py::test_x"}]}
        review = {
            "schema_version": REVIEW_SCHEMA,
            "task_id": "demo",
            "review_status": "ai_assisted_reviewed",
            "reviewer": "codex",
            "reviewed_at": "2026-08-04",
            "oracle_relation": "direct_oracle",
            "components": {
                "api_surface": {"verdict": "closed"},
                "behavior": {"verdict": "closed"},
                "dependency_environment": {"verdict": "closed"},
            },
            "tests": [
                {
                    "nodeid": "hidden_tests/test_x.py::test_x",
                    "verdict": "closed",
                    "evidence_basis": ["public_spec:B001"],
                }
            ],
            "overall_verdict": "closed",
            "revision_required": False,
        }
        self.assertEqual(validate_review(review, task), [])
        review["tests"][0]["evidence_basis"] = []
        self.assertIn("evidence_basis is required", "\n".join(validate_review(review, task)))


if __name__ == "__main__":
    unittest.main()
