from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "merge_openhands_pilot.py"
_SPEC = importlib.util.spec_from_file_location("merge_openhands_pilot", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
merge_openhands_pilot = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(merge_openhands_pilot)


class MergeOpenHandsPilotTests(unittest.TestCase):
    def test_merge_pilot_suites_writes_five_task_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sanity = root / "sanity3"
            batch = root / "batch2"
            output = root / "pilot"
            _write_suite(sanity, ["sanity_a", "sanity_b", "sanity_c"])
            _write_suite(batch, ["arrow__parse_format_core__001", "bleach__sanitize_core__001"])

            payload = merge_openhands_pilot.merge_pilot_suites(output, [sanity, batch])

            summary_json = output / "pilot5-summary.json"
            summary_md = output / "pilot5-summary.md"
            self.assertEqual(payload["summary"]["total"], 5)
            self.assertEqual(payload["summary"]["passed"], 5)
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            written = json.loads(summary_json.read_text(encoding="utf-8"))
            self.assertEqual(written["summary"]["total"], 5)


def _write_suite(suite_dir: Path, task_ids: list[str]) -> None:
    suite_dir.mkdir(parents=True)
    runs = []
    for task_id in task_ids:
        run_dir = suite_dir / task_id
        run_dir.mkdir()
        run_path = run_dir / "run.json"
        run = {
            "task_id": task_id,
            "status": "passed",
            "run_json": str(run_path),
            "agent": {
                "passed": True,
                "usage": {
                    "available": True,
                    "api_calls": 1,
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
            "submission": {"exists": True, "recovered": False},
            "evaluation": {
                "result_json": str(run_dir / "eval" / "result.json"),
                "scores": {"final_score": 1.0},
            },
        }
        run_path.write_text(json.dumps(run), encoding="utf-8")
        runs.append({"task_id": task_id, "status": "passed", "run_json": str(run_path)})
    suite = {
        "mode": "suite",
        "summary": {"total": len(task_ids), "passed": len(task_ids), "failed": 0},
        "runs": runs,
    }
    (suite_dir / "suite.json").write_text(json.dumps(suite), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
