"""Tests for Go evaluator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.checks import find_forbidden_go_imports
from featureliftbench.go_eval import _patch_go_mod_replace
from featureliftbench.metrics import count_go_loc
from featureliftbench.validate import validate_task


class GoMetricsTests(unittest.TestCase):
    def test_count_go_loc_skips_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.go"
            path.write_text(
                "// comment\npackage main\n\nfunc main() {\n}\n",
                encoding="utf-8",
            )
            self.assertEqual(count_go_loc(tmp), 3)


class GoForbiddenImportTests(unittest.TestCase):
    def test_detects_forbidden_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.go").write_text(
                'package main\nimport "github.com/bad/lib"\n',
                encoding="utf-8",
            )
            issues = find_forbidden_go_imports(root, ["github.com/bad/lib"])
            self.assertEqual(len(issues), 1)


class GoModPatchTests(unittest.TestCase):
    def test_patch_adds_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            go_mod = Path(tmp) / "go.mod"
            go_mod.write_text("module featureliftbench/eval\n\ngo 1.22\n", encoding="utf-8")
            _patch_go_mod_replace(go_mod, "featurelifted", "./submission")
            text = go_mod.read_text(encoding="utf-8")
            self.assertIn("replace featurelifted => ./submission", text)


class GoValidateTests(unittest.TestCase):
    def test_valid_go_task_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = _make_go_task(Path(tmp), "hello_featurelifted__001")
            result = validate_task(task_dir)
            self.assertTrue(result.valid, result.errors)


def _make_go_task(root: Path, dirname: str) -> Path:
    task_dir = root / dirname
    (task_dir / "repo").mkdir(parents=True)
    (task_dir / "public_tests").mkdir()
    (task_dir / "hidden_tests").mkdir()
    (task_dir / "evaluation").mkdir()
    (task_dir / "environment").mkdir()
    (task_dir / "public_tests" / "public_test.go").write_text(
        'package publictests\n',
        encoding="utf-8",
    )
    (task_dir / "hidden_tests" / "hidden_test.go").write_text(
        'package hiddentests\n',
        encoding="utf-8",
    )
    (task_dir / "evaluation" / "forbidden_imports.txt").write_text(
        "originalpkg\n",
        encoding="utf-8",
    )
    (task_dir / "environment" / "go.mod").write_text(
        "module featureliftbench/eval\n\ngo 1.22\n",
        encoding="utf-8",
    )
    metadata = {
        "task_id": dirname,
        "language": "go",
        "difficulty": "easy",
        "source": {
            "name": "sample",
            "url": "https://example.com/sample",
            "commit": "abc123",
            "license": "MIT",
        },
        "feature": {
            "name": "sample",
            "description": "sample",
            "source_entrypoints": ["sample.F"],
            "included_behaviors": ["add"],
            "excluded_behaviors": ["cli"],
        },
        "entanglement": {
            "level": "low",
            "types": ["implicit_dependency_coupling"],
            "description": "low",
            "signals": ["small"],
        },
        "output": {
            "package": "featurelifted",
            "import": "featurelifted",
            "callable": "featurelifted.Add",
            "signature": "Add(a, b int) int",
        },
        "environment": {
            "go": "1.22",
            "network": False,
            "timeout_seconds": 60,
            "cgo_enabled": False,
            "module_path": "featurelifted",
            "forbidden_imports": ["originalpkg"],
        },
        "tests": {
            "public": "public_tests",
            "hidden": "hidden_tests",
            "command": "go test",
        },
    }
    (task_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return task_dir


if __name__ == "__main__":
    unittest.main()
