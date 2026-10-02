from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from featureliftbench.go_quality import go_no_stub_gate


class GoQualityGateTests(unittest.TestCase):
    def test_blocks_non_sanity_hello_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_id = "uuid__parse_format_core__001"
            task_dir = root / "benchmark" / "go" / "tasks" / task_id
            (task_dir / "repo").mkdir(parents=True)
            (task_dir / "repo" / "add.go").write_text(
                "package originalpkg\n\nfunc Add(a, b int) int { return a + b }\n",
                encoding="utf-8",
            )
            (task_dir / "TASK.md").write_text("# Task: hello_featurelifted__001\n", encoding="utf-8")

            result = go_no_stub_gate(task_id, task_dir, repo_root=root)

            self.assertFalse(result["passed"])
            self.assertIn("G0_stub_repo_add_go", result["blocking_gates"])
            self.assertIn("G0_stub_task_prompt", result["blocking_gates"])
            self.assertIn("G0_design_note_missing", result["blocking_gates"])

    def test_allows_named_sanity_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_id = "hello_featurelifted__001"
            task_dir = root / "benchmark" / "go" / "sanity" / task_id
            (task_dir / "repo").mkdir(parents=True)
            (task_dir / "repo" / "add.go").write_text(
                "package originalpkg\n\nfunc Add(a, b int) int { return a + b }\n",
                encoding="utf-8",
            )

            result = go_no_stub_gate(task_id, task_dir, repo_root=root)

            self.assertTrue(result["passed"])
            self.assertTrue(result["details"]["sanity_exempt"])

    def test_passes_real_multi_file_task_with_design_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_id = "semver__version_parse_core__001"
            task_dir = root / "benchmark" / "go" / "tasks" / task_id
            (task_dir / "repo").mkdir(parents=True)
            (task_dir / "repo" / "version.go").write_text("package semver\n", encoding="utf-8")
            (task_dir / "repo" / "compare.go").write_text("package semver\n", encoding="utf-8")
            (task_dir / "TASK.md").write_text(f"# Task: {task_id}\n", encoding="utf-8")
            (root / "docs" / "go_task_designs").mkdir(parents=True)
            (root / "docs" / "go_task_designs" / f"{task_id}.md").write_text(
                "# Design\n",
                encoding="utf-8",
            )

            result = go_no_stub_gate(task_id, task_dir, repo_root=root)

            self.assertTrue(result["passed"], result["blocking_gates"])
