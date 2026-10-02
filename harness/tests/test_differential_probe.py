from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from featureliftbench.differential_probe import ProbeValidationError
from featureliftbench.differential_probe import load_probe_audit
from featureliftbench.differential_probe import run_differential_probe
from featureliftbench.differential_probe import upstream_runtime_dependencies
from featureliftbench.differential_probe import validate_probe


class DifferentialProbeTests(unittest.TestCase):
    def _workspace(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "repo").mkdir()
        (root / "submission").mkdir()
        (root / ".dpr" / "baseline_submission").mkdir(parents=True)
        (root / "probes").mkdir()
        (root / "repo" / "example.py").write_text(
            "VALUE = ['upstream']\n", encoding="utf-8"
        )
        (root / "submission" / "example.py").write_text(
            "VALUE = ['candidate']\n", encoding="utf-8"
        )
        (root / ".dpr" / "baseline_submission" / "example.py").write_text(
            "VALUE = ['candidate']\n", encoding="utf-8"
        )
        return temp, root

    def test_runs_same_observation_probe_against_both_targets(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        probe = root / "probes" / "value.py"
        probe.write_text(
            "import json\n"
            "from example import VALUE\n"
            "print(json.dumps({'value': VALUE}, sort_keys=True))\n",
            encoding="utf-8",
        )

        result = run_differential_probe(
            root,
            probe,
            python_executable=sys.executable,
        )

        self.assertTrue(result["observations_comparable"])
        self.assertFalse(result["observations_equal"])
        self.assertEqual(result["upstream"]["observation"], {"value": ["upstream"]})
        self.assertEqual(result["candidate"]["observation"], {"value": ["candidate"]})
        audit = load_probe_audit(root)
        self.assertTrue(audit["tool_used"])
        self.assertEqual(audit["records"], 1)
        self.assertEqual(audit["unequal_records"], 1)

    def test_equal_observations_are_reported(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        (root / "submission" / "example.py").write_text(
            "VALUE = ['upstream']\n", encoding="utf-8"
        )
        probe = root / "probes" / "value.py"
        probe.write_text(
            "import json\n"
            "from example import VALUE\n"
            "print(json.dumps(VALUE))\n",
            encoding="utf-8",
        )

        result = run_differential_probe(root, probe)

        self.assertTrue(result["observations_comparable"])
        self.assertTrue(result["observations_equal"])

    def test_paired_probe_uses_upstream_target_and_baseline_control(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        probe = root / "probes" / "paired.py"
        probe.write_text(
            "import json\n"
            "from example import VALUE\n"
            "print(json.dumps("
            "{'target': {'value': VALUE}, "
            "'control': {'stable': 'stable'}}))\n",
            encoding="utf-8",
        )

        initial = run_differential_probe(
            root,
            probe,
            include_baseline=True,
            require_paired=True,
            single_probe=True,
            max_calls=4,
        )
        self.assertFalse(initial["target_matches_upstream"])
        self.assertTrue(initial["control_preserved_from_baseline"])

        (root / "submission" / "example.py").write_text(
            "VALUE = ['upstream']\n", encoding="utf-8"
        )
        repaired = run_differential_probe(
            root,
            probe,
            include_baseline=True,
            require_paired=True,
            single_probe=True,
            max_calls=4,
        )
        self.assertTrue(repaired["target_matches_upstream"])
        self.assertTrue(repaired["control_preserved_from_baseline"])
        audit = load_probe_audit(root)
        self.assertTrue(audit["one_frozen_probe"])
        self.assertTrue(audit["repair_accepted"])
        self.assertEqual(audit["control_regression_records"], 0)

    def test_paired_probe_requires_target_and_control(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        probe = root / "probes" / "unpaired.py"
        probe.write_text(
            "import json\n"
            "print(json.dumps({'value': 1}))\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ProbeValidationError, "top-level"):
            run_differential_probe(
                root,
                probe,
                include_baseline=True,
                require_paired=True,
            )

    def test_first_actionable_probe_is_frozen(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        probe = root / "probes" / "paired.py"
        probe.write_text(
            "import json\n"
            "from example import VALUE\n"
            "print(json.dumps("
            "{'target': {'value': VALUE}, 'control': {'stable': 1}}))\n",
            encoding="utf-8",
        )
        run_differential_probe(
            root,
            probe,
            include_baseline=True,
            require_paired=True,
            single_probe=True,
        )
        probe.write_text(
            "import json\n"
            "from example import VALUE\n"
            "print(json.dumps("
            "{'target': {'value': VALUE}, 'control': {'stable': 2}}))\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ProbeValidationError, "is frozen"):
            run_differential_probe(
                root,
                probe,
                include_baseline=True,
                require_paired=True,
                single_probe=True,
            )

    def test_equal_probe_does_not_freeze_the_search(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        equal_probe = root / "probes" / "equal.py"
        equal_probe.write_text(
            "import json\n"
            "print(json.dumps("
            "{'target': {'stable': 1}, 'control': {'stable': 1}}))\n",
            encoding="utf-8",
        )
        run_differential_probe(
            root,
            equal_probe,
            include_baseline=True,
            require_paired=True,
            single_probe=True,
        )
        next_probe = root / "probes" / "next.py"
        next_probe.write_text(
            "import json\n"
            "from example import VALUE\n"
            "print(json.dumps("
            "{'target': {'value': VALUE}, 'control': {'stable': 1}}))\n",
            encoding="utf-8",
        )

        result = run_differential_probe(
            root,
            next_probe,
            include_baseline=True,
            require_paired=True,
            single_probe=True,
        )

        self.assertFalse(result["target_matches_upstream"])
        self.assertTrue(result["control_preserved_from_baseline"])

    def test_assert_is_rejected(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        probe = root / "probes" / "bad.py"
        probe.write_text("assert 1 == 1\n", encoding="utf-8")

        with self.assertRaisesRegex(ProbeValidationError, "must not contain assert"):
            validate_probe(probe)

    def test_evaluator_reference_is_rejected(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        probe = root / "probes" / "bad.py"
        probe.write_text(
            "import json\n"
            "print(json.dumps({'path': 'hidden_tests/test_contract.py'}))\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ProbeValidationError, "forbidden evaluator"):
            validate_probe(probe)

    def test_probe_must_be_inside_workspace(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        external = Path(tempfile.mkstemp(suffix=".py")[1])
        self.addCleanup(external.unlink)
        external.write_text("print(json.dumps({}))\n", encoding="utf-8")

        with self.assertRaisesRegex(ProbeValidationError, "inside the workspace"):
            run_differential_probe(root, external)

    def test_audit_summary_tolerates_invalid_lines(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        audit_dir = root / ".dpr"
        audit_dir.mkdir(exist_ok=True)
        (audit_dir / "audit.jsonl").write_text(
            json.dumps(
                {
                    "observations_comparable": True,
                    "observations_equal": False,
                }
            )
            + "\nnot-json\n",
            encoding="utf-8",
        )

        audit = load_probe_audit(root)

        self.assertEqual(audit["records"], 1)
        self.assertEqual(len(audit["errors"]), 1)
        self.assertFalse(audit["protocol_compliant"])

    def test_reads_declared_upstream_runtime_dependencies(self) -> None:
        temp, root = self._workspace()
        self.addCleanup(temp.cleanup)
        (root / "repo" / "pyproject.toml").write_text(
            "[project]\n"
            "name = 'example'\n"
            "version = '1.0'\n"
            "dependencies = ['SQLAlchemy>=1.4', 'typing-extensions']\n",
            encoding="utf-8",
        )

        dependencies = upstream_runtime_dependencies(root)

        self.assertEqual(
            dependencies,
            ["SQLAlchemy>=1.4", "typing-extensions"],
        )


if __name__ == "__main__":
    unittest.main()
