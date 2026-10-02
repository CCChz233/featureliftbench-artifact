from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from featureliftbench.run_workflow import _run_lock


class RunWorkflowTests(unittest.TestCase):
    def test_run_lock_creates_missing_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "new-run"

            with _run_lock(output_dir):
                self.assertTrue(output_dir.is_dir())
                self.assertTrue((output_dir / ".run.lock" / "pid").is_file())

            self.assertFalse((output_dir / ".run.lock").exists())
