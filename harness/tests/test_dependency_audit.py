from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.dependency_audit import (
    audit_task_dependencies,
    parse_oracle_runtime_dependencies,
    validate_lock_allowed_consistency,
)


class DependencyAuditTests(unittest.TestCase):
    def test_validate_lock_allowed_consistency_empty_lock_with_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            metadata = {
                "language": "python",
                "environment": {
                    "dependency_lock": "requirements.lock",
                    "allowed_dependencies": ["python-dateutil"],
                },
            }
            (task_dir / "requirements.lock").write_text("", encoding="utf-8")

            errors = validate_lock_allowed_consistency(metadata, task_dir)

            self.assertEqual(len(errors), 1)
            self.assertIn("requirements.lock is empty", errors[0])

    def test_parse_oracle_runtime_dependencies_ignores_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "oracle_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "runtime_dependencies": [
                            "python-dateutil",
                            "PyYAML via allowed_dependencies; empty lock",
                        ]
                    }
                ),
                encoding="utf-8",
            )

            names = parse_oracle_runtime_dependencies(manifest)

            self.assertEqual(names, ["python-dateutil", "pyyaml"])

    def test_audit_task_flags_missing_wheel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "sample_task"
            (task_dir / "repo").mkdir(parents=True)
            (task_dir / "public_tests").mkdir()
            (task_dir / "hidden_tests").mkdir()
            (task_dir / "evaluation").mkdir()
            (task_dir / "evaluation" / "oracle_manifest.json").write_text("{}", encoding="utf-8")
            missing_package = "featureliftbench-missing-wheel-fixture"
            (task_dir / "requirements.lock").write_text(
                f"{missing_package}==1.0.0\n", encoding="utf-8"
            )
            (task_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "task_id": "sample_task",
                        "language": "python",
                        "environment": {
                            "dependency_lock": "requirements.lock",
                            "allowed_dependencies": [missing_package],
                        },
                    }
                ),
                encoding="utf-8",
            )

            audit = audit_task_dependencies(task_dir, check_oracle_manifest=False)

            self.assertFalse(audit.ok)
            self.assertTrue(
                any(issue.kind == "lock_package_missing_wheel" for issue in audit.issues),
                audit.issues,
            )


if __name__ == "__main__":
    unittest.main()
