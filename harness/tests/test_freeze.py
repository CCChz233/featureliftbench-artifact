from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from featureliftbench.freeze import file_manifest
from featureliftbench.freeze import manifest_digest
from featureliftbench.freeze import verify_file_manifest


class FreezeTests(unittest.TestCase):
    def test_manifest_detects_content_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "TASK.md"
            path.write_text("v1\n", encoding="utf-8")
            expected = file_manifest([path], root=root)

            self.assertEqual(verify_file_manifest(expected, root=root), [])
            path.write_text("v2\n", encoding="utf-8")
            mismatches = verify_file_manifest(expected, root=root)

            self.assertEqual(len(mismatches), 1)
            self.assertEqual(mismatches[0]["path"], "TASK.md")

    def test_manifest_digest_ignores_generated_time_and_freeze_id(self) -> None:
        left = {"generated_at": "a", "freeze_id": "x", "files": {"a": "b"}}
        right = {"generated_at": "b", "freeze_id": "y", "files": {"a": "b"}}

        self.assertEqual(manifest_digest(left), manifest_digest(right))

    def test_local_agent_configs_are_not_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            tracked = config / "agents.example.toml"
            local = config / "agents.toml"
            tracked.write_text("profile = \"example\"\n", encoding="utf-8")
            local.write_text("profile = \"local-model\"\n", encoding="utf-8")

            manifest = file_manifest([config], root=root)
            self.assertIn("config/agents.example.toml", manifest)
            self.assertNotIn("config/agents.toml", manifest)

            # Legacy freezes may still list agents.toml; verification must ignore it.
            legacy = dict(manifest)
            legacy["config/agents.toml"] = "deadbeef"
            local.write_text("profile = \"changed\"\n", encoding="utf-8")
            self.assertEqual(verify_file_manifest(legacy, root=root), [])


if __name__ == "__main__":
    unittest.main()
