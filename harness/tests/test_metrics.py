from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from featureliftbench.metrics import count_files
from featureliftbench.metrics import count_python_loc
from featureliftbench.metrics import count_runtime_dependencies
from featureliftbench.metrics import count_suspicious_files
from featureliftbench.metrics import dependency_name
from featureliftbench.metrics import directory_size_bytes
from featureliftbench.metrics import find_declared_runtime_dependencies


class MetricsTests(unittest.TestCase):
    def test_basic_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module.py").write_text(
                "\n# comment\nvalue = 1\n\nprint(value)\n",
                encoding="utf-8",
            )
            (root / "data.txt").write_text("abc", encoding="utf-8")

            self.assertEqual(count_files(root), 2)
            self.assertEqual(count_python_loc(root), 2)
            self.assertGreater(directory_size_bytes(root), 0)

    def test_count_runtime_dependencies_from_pyproject_and_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project]\n"
                "dependencies = ['Requests>=2', 'attrs']\n",
                encoding="utf-8",
            )
            (root / "requirements.txt").write_text(
                "# ignored\n"
                "requests==2.0\n"
                "packaging>=24\n",
                encoding="utf-8",
            )

            self.assertEqual(count_runtime_dependencies(root), 3)
            self.assertEqual(
                find_declared_runtime_dependencies(root),
                {"requests", "attrs", "packaging"},
            )

    def test_count_suspicious_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "featurelifted.py").write_text("", encoding="utf-8")
            (root / "README.md").write_text("", encoding="utf-8")
            testing = root / "testing"
            testing.mkdir()
            (testing / "test_sample.py").write_text("", encoding="utf-8")

            self.assertEqual(count_suspicious_files(root), 2)

    def test_dependency_name_normalizes_requirement_lines(self) -> None:
        self.assertEqual(dependency_name("Sample_Pkg>=1.0 # comment"), "sample-pkg")
        self.assertEqual(dependency_name("-r base.txt"), "")


if __name__ == "__main__":
    unittest.main()
