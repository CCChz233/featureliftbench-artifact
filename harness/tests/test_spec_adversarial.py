"""Unit tests for Spec-grounded adversarial self-test matrix + workspace."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.spec_adversarial import build_contract_matrix
from featureliftbench.spec_adversarial import install_spec_adversarial_workspace
from featureliftbench.spec_adversarial import scenario_behavior_ids


class SpecAdversarialMatrixTests(unittest.TestCase):
    def test_schema_public_spec_matrix_has_behaviors_and_api(self) -> None:
        metadata_path = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "python200_tasks"
            / "schema__nested_validate_core__hard3_001"
            / "metadata.json"
        )
        if not metadata_path.is_file():
            # Workspace layout: FeatureLiftBench/harness/tests → parents[2] is repo
            metadata_path = (
                Path(__file__).resolve().parents[2]
                / ".."
                / "benchmark"
                / "python200_tasks"
                / "schema__nested_validate_core__hard3_001"
                / "metadata.json"
            ).resolve()
        # Prefer absolute repo path used in this workspace.
        repo_meta = Path(
            "/data1/FeatureLiftBench/benchmark/python200_tasks/"
            "schema__nested_validate_core__hard3_001/metadata.json"
        )
        if repo_meta.is_file():
            metadata_path = repo_meta
        self.assertTrue(metadata_path.is_file(), msg=str(metadata_path))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        public_spec = metadata["public_spec"]
        matrix = build_contract_matrix(public_spec)
        behavior_ids = {row["id"] for row in matrix["behaviors"]}
        self.assertIn("B001", behavior_ids)
        self.assertIn("B002", behavior_ids)
        self.assertIn("B003", behavior_ids)
        self.assertIn("B004", behavior_ids)
        # Isolation B005 is listed but does not need a scenario stub.
        self.assertIn("B005", behavior_ids)
        scenario_ids = scenario_behavior_ids(matrix)
        self.assertEqual(scenario_ids, ["B001", "B002", "B003", "B004"])
        api_paths = {row["path"] for row in matrix["required_api"]}
        self.assertIn("featurelifted.Schema", api_paths)
        self.assertIn("featurelifted.SchemaError", api_paths)
        self.assertIn("featurelifted.Schema.validate", api_paths)
        dumped = json.dumps(matrix)
        self.assertNotIn("source_entrypoints", dumped)
        self.assertNotIn("schema.Schema", dumped)

    def test_install_writes_stubs_without_entrypoints(self) -> None:
        public_spec = {
            "title": "Demo",
            "summary": "Demo summary",
            "required_api": [
                {
                    "path": "featurelifted.Foo",
                    "kind": "class",
                    "members": [
                        {
                            "path": "featurelifted.Foo.bar",
                            "kind": "method",
                        }
                    ],
                },
                {"path": "featurelifted.FooError", "kind": "exception"},
            ],
            "behaviors": [
                {"id": "B001", "text": "Foo validates."},
                {"id": "B002", "text": "Foo exposes API."},
            ],
            "source_entrypoints": ["should.not.leak"],
            "exclusions": ["network"],
            "forbidden": {"imports": ["upstream_pkg"]},
            "isolation_behavior": {
                "id": "B003",
                "text": "does not import upstream_pkg",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_spec_adversarial_workspace(root, public_spec=public_spec)
            matrix = json.loads(
                (root / "contract_matrix.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("source_entrypoints", json.dumps(matrix))
            self.assertTrue((root / "run_contract_check.py").is_file())
            self.assertTrue((root / "contract_cases" / "B001.py").is_file())
            self.assertTrue((root / "contract_cases" / "B002.py").is_file())
            self.assertFalse((root / "contract_cases" / "B003.py").is_file())
            stub = (root / "contract_cases" / "B001.py").read_text(encoding="utf-8")
            self.assertIn("FILLED = False", stub)
            self.assertIn("run_featurelifted", stub)
            self.assertNotIn("should.not.leak", stub)


if __name__ == "__main__":
    unittest.main()
