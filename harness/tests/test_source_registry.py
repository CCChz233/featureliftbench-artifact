from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_source_registry.py"
SPEC = importlib.util.spec_from_file_location("build_source_registry", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
REGISTRY_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REGISTRY_MODULE)


class SourceRegistryTests(unittest.TestCase):
    def test_github_aliases_have_one_canonical_identity(self) -> None:
        first = REGISTRY_MODULE.canonicalize_url(
            "https://github.com/AIO-Libs/AIOHTTP.git"
        )
        second = REGISTRY_MODULE.canonicalize_url(
            "https://github.com/aio-libs/aiohttp/"
        )
        self.assertEqual(first, second)
        self.assertEqual(
            REGISTRY_MODULE.source_repo_id(first[0], first[1]),
            "github__aio_libs__aiohttp",
        )

    def test_tracked_registry_matches_all_python_tasks(self) -> None:
        registry_path = ROOT / "benchmark" / "sources" / "registry.json"
        tracked = json.loads(registry_path.read_text(encoding="utf-8"))
        generated = REGISTRY_MODULE.build_registry(ROOT / "benchmark" / "tasks")
        generated = REGISTRY_MODULE.merge_existing_evidence(generated, tracked)
        self.assertEqual(generated, tracked)
        self.assertEqual(REGISTRY_MODULE.validate_registry(tracked), [])
        self.assertEqual(
            tracked["summary"],
            {
                "curated_repository_count": 0,
                "external_repository_count": 126,
                "pending_snapshot_count": 0,
                "ready_snapshot_count": 132,
                "repository_count": 126,
                "snapshot_count": 132,
                "task_count": 150,
            },
        )

    def test_pilot_references_registry_and_balances_legacy_splits(self) -> None:
        registry = json.loads(
            (ROOT / "benchmark" / "sources" / "registry.json").read_text(
                encoding="utf-8"
            )
        )
        pilot = json.loads(
            (ROOT / "benchmark" / "pilots" / "full_repository_v2.json").read_text(
                encoding="utf-8"
            )
        )
        snapshots = {
            item["source_snapshot_id"]: item for item in registry["snapshots"]
        }
        tasks = pilot["tasks"]
        self.assertEqual(len(tasks), 16)
        self.assertEqual(len({item["source_repo_id"] for item in tasks}), 16)
        self.assertEqual(
            {
                split: sum(item["legacy_split"] == split for item in tasks)
                for split in ("core100", "hard50")
            },
            {"core100": 8, "hard50": 8},
        )
        for item in tasks:
            snapshot = snapshots[item["source_snapshot_id"]]
            self.assertEqual(snapshot["source_repo_id"], item["source_repo_id"])
            self.assertIn(item["task_id"], snapshot["task_ids"])
            self.assertEqual(item["status"], "selected_not_materialized")


if __name__ == "__main__":
    unittest.main()
