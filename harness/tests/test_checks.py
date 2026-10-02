from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from featureliftbench.checks import find_forbidden_imports
from featureliftbench.checks import find_forbidden_dependencies
from featureliftbench.checks import read_forbidden_imports


class ChecksTests(unittest.TestCase):
    def test_read_forbidden_imports_ignores_comments_and_blanks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forbidden_imports.txt"
            path.write_text("\n# comment\niniconfig\n\n", encoding="utf-8")

            self.assertEqual(read_forbidden_imports(path), ["iniconfig"])

    def test_find_forbidden_imports_detects_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "featurelifted.py").write_text(
                "import os\nfrom iniconfig import IniConfig\n",
                encoding="utf-8",
            )

            issues = find_forbidden_imports(root, ["iniconfig"])

            self.assertEqual(len(issues), 1)
            self.assertIn("imports from forbidden module 'iniconfig'", issues[0].format(root))

    def test_find_forbidden_imports_allows_unused_forbidden_package_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "iniconfig"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")

            issues = find_forbidden_imports(root, ["iniconfig"])

            self.assertEqual(issues, [])

    def test_find_forbidden_imports_allows_relative_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "featurelifted"
            package.mkdir()
            (package / "__init__.py").write_text("from . import _parse\n", encoding="utf-8")
            (package / "_parse.py").write_text("", encoding="utf-8")

            issues = find_forbidden_imports(root, ["iniconfig"])

            self.assertEqual(issues, [])

    def test_find_forbidden_imports_skips_non_runtime_test_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            testing = root / "testing"
            testing.mkdir()
            (testing / "test_sample.py").write_text(
                "import iniconfig\n",
                encoding="utf-8",
            )
            (root / "test.py").write_text("import iniconfig\n", encoding="utf-8")

            issues = find_forbidden_imports(root, ["iniconfig"])

            self.assertEqual(issues, [])

    def test_find_forbidden_dependencies_detects_declared_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project]\n"
                "dependencies = ['Forbidden_Pkg>=1']\n",
                encoding="utf-8",
            )

            issues = find_forbidden_dependencies(root, ["forbidden-pkg"])

            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].format(), "declares forbidden dependency 'forbidden-pkg'")


if __name__ == "__main__":
    unittest.main()
