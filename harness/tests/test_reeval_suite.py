from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reeval_suite.py"
SPEC = importlib.util.spec_from_file_location("reeval_suite", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReevalSuiteTests(unittest.TestCase):
    def test_clone_suite_copies_inputs_without_touching_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            task = source / "sample"
            (task / "submission" / "featurelifted").mkdir(parents=True)
            (task / "submission" / "featurelifted" / "__init__.py").write_text("VALUE = 1\n")
            (task / "run.json").write_text(json.dumps({"task_id": "sample"}))
            (source / "suite.json").write_text(json.dumps({"runs": [{"task_id": "sample"}]}))
            source_before = (task / "run.json").read_bytes()

            MODULE.clone_suite_for_immutable_reeval(source, destination, ["sample"])

            self.assertEqual((task / "run.json").read_bytes(), source_before)
            self.assertTrue((destination / "sample" / "run.json").is_file())
            self.assertTrue((destination / "sample" / "submission" / "featurelifted" / "__init__.py").is_file())
            provenance = json.loads((destination / "reeval_source.json").read_text())
            self.assertFalse(provenance["source_mutable"])


if __name__ == "__main__":
    unittest.main()
