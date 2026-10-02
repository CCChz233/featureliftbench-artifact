from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.experiment_paths import resolve_experiment_path


class ExperimentPathTests(unittest.TestCase):
    def test_longest_prefix_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alias_file = root / "aliases.json"
            alias_file.write_text(
                json.dumps(
                    {
                        "schema_version": "featureliftbench.experiment_path_aliases.v1",
                        "aliases": [
                            {"old_prefix": "experiments/a", "new_prefix": "experiments/x"},
                            {
                                "old_prefix": "experiments/a/specific",
                                "new_prefix": "experiments/y",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = resolve_experiment_path(
                "experiments/a/specific/run.json",
                repo_root=root,
                alias_file=alias_file,
            )
            self.assertEqual(resolved, root / "experiments/y/run.json")

    def test_unknown_path_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_experiment_path(
                "experiments/python/run.json",
                repo_root=root,
                alias_file=root / "missing.json",
            )
            self.assertEqual(resolved, root / "experiments/python/run.json")


if __name__ == "__main__":
    unittest.main()
