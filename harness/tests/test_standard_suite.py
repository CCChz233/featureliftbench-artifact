from __future__ import annotations

import json
import unittest
from pathlib import Path

from featureliftbench.paths import REPO_ROOT


PARENT = REPO_ROOT / "benchmark" / "selection" / "python200_hard_suite.json"
SELECTION = REPO_ROOT / "benchmark" / "selection" / "python200_hard_standard_suite.json"
EXCLUDED = REPO_ROOT / "benchmark" / "selection" / "python200_hard_excluded.json"
TASK_FILE = REPO_ROOT / "harness" / "config" / "experiments" / "python200_hard_standard.txt"


class StandardSuiteTests(unittest.TestCase):
    """v2 published analysis subset partitions the parent 200.

    ``python200_hard_standard_suite.json`` is the protocol-v2
    ``meets_standard`` list after freeze v2 repair (200/0, undetermined=0).
    The predecessor 168/32 cut is archived; this list now matches the parent 200.
    """
    def test_standard_subset_partitions_the_parent_suite(self) -> None:
        parent = json.loads(PARENT.read_text(encoding="utf-8"))
        selection = json.loads(SELECTION.read_text(encoding="utf-8"))
        excluded = json.loads(EXCLUDED.read_text(encoding="utf-8"))
        keep = selection["task_ids"]
        drop = [row["task_id"] for row in excluded["tasks"]]
        parent_ids = parent["task_ids"]

        self.assertEqual(selection["parent_suite_id"], parent["suite_id"])
        self.assertEqual(len(keep), selection["task_count"])
        self.assertEqual(len(drop), excluded["n"])
        self.assertEqual(len(keep) + len(drop), len(parent_ids))
        self.assertEqual(set(keep) | set(drop), set(parent_ids))
        self.assertFalse(set(keep) & set(drop))
        self.assertEqual(keep, sorted(keep))
        self.assertTrue(all(row["failed_rules"] for row in excluded["tasks"]))

        listed = [
            line.strip()
            for line in TASK_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertEqual(listed, keep)
        self.assertTrue(Path(TASK_FILE).is_file())


if __name__ == "__main__":
    unittest.main()
