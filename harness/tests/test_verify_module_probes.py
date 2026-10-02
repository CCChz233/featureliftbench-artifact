from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from verify_module_probes import audit_design_coverage, parse_module_probes


class VerifyModuleProbesTests(unittest.TestCase):
    def test_parse_module_probes_from_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            design = Path(tmp) / "sample__task__001.md"
            design.write_text(
                """# Task Design: sample__task__001

## Module Probes

| Probe | Remove module | Hidden test(s) that must fail |
| --- | --- | --- |
| Core parser | `parser.py` | `test_parse_basic` |
| Error types | `errors.py` | `test_raises_parse_error` |
| Loader | `loaders/base.py` | `test_missing_template` |
""",
                encoding="utf-8",
            )
            probes = parse_module_probes(design)
            self.assertEqual(len(probes), 3)
            self.assertEqual(probes[0]["remove_paths"], ["parser.py"])
            self.assertEqual(probes[0]["must_fail_tests"], ["test_parse_basic"])

    def test_declared_task_designs_have_min_probes(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        tasks_dir = repo_root / "benchmark" / "tasks"
        task_dirs = sorted(
            path for path in tasks_dir.iterdir() if path.is_dir() and (path / "metadata.json").is_file()
        )
        audit = audit_design_coverage(task_dirs, min_probes=3)
        # Module-probe design notes are an optional, stronger audit gate. If a
        # task opts in, require a complete probe set; their absence alone is not
        # a main-split lifecycle failure.
        gaps = [item for item in audit if item["design_present"] and not item["ok"]]
        self.assertEqual(
            gaps,
            [],
            msg="Declared task designs with fewer than 3 module probes: "
            + ", ".join(str(item["task_id"]) for item in gaps),
        )


if __name__ == "__main__":
    unittest.main()
