from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.benchmark_freeze import benchmark_freeze_provenance


def _write_freeze(path: Path, *, task_count: int, extra_task: dict | None = None) -> None:
    tasks = {
        "demo__core__001": {
            "generated_task_hash": "abc",
            "source_archive_sha256": "arch",
            "source_snapshot_id": "snap",
            "source_tree_sha256": "tree",
            "spec_hash": "spec",
            "stratum": "hard50" if task_count == 200 else "python150",
            "task_revision": 1,
        }
    }
    if extra_task:
        tasks.update(extra_task)
    payload = {
        "freeze_id": "freeze-200" if task_count == 200 else "freeze-150",
        "gate_pass": True,
        "policy_id": "featureliftbench.full_repository_no_hint_main.v3",
        "primary_metric": "functional_pass_at_1",
        "split": "python200_prime" if task_count == 200 else "python-external-main-150",
        "task_count": task_count,
        "tasks": tasks,
    }
    if task_count == 200:
        payload["images"] = {"agent": {"tag": "featureliftbench-agent:python200-prime-212930ea"}}
    else:
        payload["environment"] = {
            "images": {"agent": {"tag": "featureliftbench-agent:python200-prime-769f2486"}}
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


class BenchmarkFreezeTests(unittest.TestCase):
    def test_python200_prime_freeze_records_hard50_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            freeze = Path(tmp) / "freeze.json"
            _write_freeze(freeze, task_count=200)
            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_BENCHMARK_FREEZE": str(freeze)},
                clear=False,
            ):
                proven = benchmark_freeze_provenance("demo__core__001", require=True)

        self.assertEqual(proven["freeze_id"], "freeze-200")
        self.assertEqual(proven["stratum"], "hard50")
        self.assertEqual(
            proven["environment"]["images"]["agent"]["tag"],
            "featureliftbench-agent:python200-prime-212930ea",
        )

    def test_python150_freeze_still_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            freeze = Path(tmp) / "freeze.json"
            _write_freeze(freeze, task_count=150)
            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_BENCHMARK_FREEZE": str(freeze)},
                clear=False,
            ):
                proven = benchmark_freeze_provenance("demo__core__001", require=True)

        self.assertEqual(proven["freeze_id"], "freeze-150")
        self.assertEqual(proven["stratum"], "python150")

    def test_missing_hard50_task_is_optional_when_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            freeze = Path(tmp) / "freeze.json"
            _write_freeze(freeze, task_count=150)
            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_BENCHMARK_FREEZE": str(freeze)},
                clear=False,
            ):
                self.assertIsNone(
                    benchmark_freeze_provenance("anyio__task_group_core__001")
                )


if __name__ == "__main__":
    unittest.main()
