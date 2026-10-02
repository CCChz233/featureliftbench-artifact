from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "archive" / "audit_new_protocol_readiness.py"
SPEC = importlib.util.spec_from_file_location("audit_new_protocol_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT_MODULE)


def _write_task(root: Path, task_id: str, *, ready: bool) -> None:
    task_dir = root / task_id
    (task_dir / "repo" / "package").mkdir(parents=True)
    (task_dir / "repo" / "package" / "feature.py").write_text(
        "def extract(value):\n    return value\n",
        encoding="utf-8",
    )
    if ready:
        (task_dir / "repo" / "tests").mkdir()
        (task_dir / "repo" / "tests" / "test_feature.py").write_text(
            "def test_extract():\n    assert True\n",
            encoding="utf-8",
        )
    metadata = {
        "spec_status": "compliant",
        "public_spec": {
            "required_api": [
                {
                    "kind": "function",
                    "path": "package.feature.extract",
                    **({"signature": "extract(value)"} if ready else {}),
                }
            ],
            "behaviors": [
                {
                    "id": "behavior-1",
                    "text": (
                        "extract(value) returns the supplied value unchanged"
                        if ready
                        else "preserves the corresponding upstream-observable "
                        "result within the documented scope"
                    ),
                }
            ],
        },
        "evaluation_spec": {},
    }
    (task_dir / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


class NewProtocolReadinessAuditTests(unittest.TestCase):
    def test_audit_uses_contract_and_package_gates_without_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = Path(tmp)
            _write_task(tasks_root, "ready", ready=True)
            _write_task(tasks_root, "needs_content_work", ready=False)
            (
                tasks_root
                / "ready"
                / "repo"
                / "tests"
                / "test_feature.py"
            ).unlink()

            report = AUDIT_MODULE.audit(tasks_root)

        self.assertEqual(report["summary"]["task_count"], 2)
        self.assertEqual(report["summary"]["engineering_ready"], 2)
        self.assertEqual(report["summary"]["contract_ready"], 1)
        self.assertEqual(report["summary"]["experiment_ready"], 1)
        self.assertEqual(report["summary"]["content_ready"], 1)
        self.assertEqual(report["summary"]["repository_discovery_ready"], 0)
        failing = next(
            task for task in report["tasks"] if task["task_id"] == "needs_content_work"
        )
        self.assertIn("generic_behavior_contract", failing["issues"])
        self.assertIn("missing_callable_signatures", failing["issues"])
        self.assertNotIn("independent_human_review_pending", failing["issues"])


if __name__ == "__main__":
    unittest.main()
