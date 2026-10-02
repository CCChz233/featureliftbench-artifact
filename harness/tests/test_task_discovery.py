from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.paths import SANITY_TASKS_DIR, TASKS_DIR
from featureliftbench.task_discovery import (
    discover_main_task_dirs,
    discover_sanity_task_dirs,
)


class TaskDiscoveryTests(unittest.TestCase):
    def test_main_tasks_are_hard_only_by_default(self) -> None:
        task_dirs = discover_main_task_dirs(TASKS_DIR, hard_only=True)
        for task_dir in task_dirs:
            metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata.get("difficulty"), "hard", task_dir.name)

    def test_sanity_tasks_are_not_hard(self) -> None:
        if not SANITY_TASKS_DIR.is_dir():
            self.skipTest("sanity directory missing")
        for task_dir in discover_sanity_task_dirs():
            metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertIn(metadata.get("difficulty"), {"easy", "medium"})

    def test_sanity_has_three_smoke_tasks(self) -> None:
        if not SANITY_TASKS_DIR.is_dir():
            self.skipTest("sanity directory missing")
        self.assertEqual(len(discover_sanity_task_dirs()), 3)


if __name__ == "__main__":
    unittest.main()
