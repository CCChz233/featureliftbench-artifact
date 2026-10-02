from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.metadata import (
    ENTANGLEMENT_PRIMARY_TYPES,
    load_metadata,
    validate_metadata_shape,
)


class MetadataTests(unittest.TestCase):
    def test_load_metadata_from_task_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "sample_task"
            task_dir.mkdir()
            (task_dir / "metadata.json").write_text(
                json.dumps(_valid_metadata("sample_task")),
                encoding="utf-8",
            )

            metadata = load_metadata(task_dir)

            self.assertEqual(metadata.task_id, "sample_task")

    def test_validate_metadata_shape_reports_missing_fields(self) -> None:
        errors = validate_metadata_shape({"task_id": "sample"})

        self.assertIn("missing required field: language", errors)
        self.assertIn("missing required field: source", errors)

    def test_validate_metadata_shape_accepts_valid_metadata(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["difficulty"] = "medium"
        metadata["tags"] = ["parser", "pure-python"]

        errors = validate_metadata_shape(metadata)

        self.assertEqual(errors, [])

    def test_validate_metadata_shape_rejects_unknown_difficulty(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["difficulty"] = "extreme"

        errors = validate_metadata_shape(metadata)

        self.assertIn("field difficulty must be one of: easy, medium, hard", errors)

    def test_validate_metadata_shape_accepts_mechanism_challenging_split_role(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["split_role"] = "mechanism_challenging"

        self.assertEqual(validate_metadata_shape(metadata), [])

    def test_validate_metadata_shape_rejects_unknown_split_role(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["split_role"] = "harder"

        self.assertIn(
            "field split_role must be: mechanism_challenging",
            validate_metadata_shape(metadata),
        )

    def test_validate_metadata_shape_rejects_unknown_entanglement_type(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["entanglement"]["types"] = ["mystery_coupling"]

        errors = validate_metadata_shape(metadata)

        self.assertIn(
            "field entanglement.types contains unknown values: mystery_coupling",
            errors,
        )

    def test_validate_metadata_shape_accepts_entanglement_primary(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["entanglement"]["types"] = [
            "parser_state_coupling",
            "implicit_dependency_coupling",
        ]
        metadata["entanglement"]["primary"] = "parser_state_coupling"

        errors = validate_metadata_shape(metadata)

        self.assertEqual(errors, [])

    def test_validate_metadata_shape_rejects_primary_not_in_types(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["entanglement"]["types"] = ["implicit_dependency_coupling"]
        metadata["entanglement"]["primary"] = "framework_coupling"

        errors = validate_metadata_shape(metadata)

        self.assertIn(
            "field entanglement.primary must also appear in entanglement.types: framework_coupling",
            errors,
        )

    def test_validate_metadata_shape_rejects_secondary_only_primary(self) -> None:
        metadata = _valid_metadata("sample_task")
        metadata["entanglement"]["types"] = [
            "implicit_dependency_coupling",
            "global_state_registry_coupling",
        ]
        metadata["entanglement"]["primary"] = "implicit_dependency_coupling"

        errors = validate_metadata_shape(metadata)

        self.assertIn(
            "field entanglement.primary must be one of: "
            + ", ".join(ENTANGLEMENT_PRIMARY_TYPES),
            errors,
        )


def _valid_metadata(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "language": "python",
        "source": {
            "name": "sample",
            "url": "https://example.com/sample",
            "commit": "abc123",
            "license": "MIT",
        },
        "feature": {
            "name": "sample feature",
            "description": "A sample feature.",
            "source_entrypoints": ["sample.parse"],
            "included_behaviors": ["parse input"],
            "excluded_behaviors": [],
        },
        "entanglement": {
            "level": "low",
            "types": ["implicit_dependency_coupling"],
            "description": "Sample task with a small import boundary.",
            "signals": ["single source entrypoint", "no framework runtime"],
        },
        "output": {
            "package": "featurelifted",
            "import": "from featurelifted import parse",
            "callable": "featurelifted.parse",
            "signature": "parse(text)",
        },
        "environment": {
            "python": "3.11",
            "network": False,
            "timeout_seconds": 60,
            "dependency_lock": "requirements.lock",
            "allowed_dependencies": [],
            "forbidden_dependencies": ["sample"],
            "forbidden_imports": ["sample"],
        },
        "tests": {
            "public": "public_tests/",
            "hidden": "hidden_tests/",
            "command": "pytest",
        },
        "scoring_reference": {
            "copy_all_bytes": 100,
            "copy_all_loc": 10,
            "oracle_bytes": 50,
            "oracle_loc": 5,
            "oracle_dependency_count": 0,
        },
    }


if __name__ == "__main__":
    unittest.main()
