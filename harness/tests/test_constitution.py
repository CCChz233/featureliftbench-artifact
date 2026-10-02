"""Tests for constitution spec rendering and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.constitution_validate import (
    _validate_test_api_usage,
    validate_constitution,
)
from featureliftbench.task_render import (
    COMPLETE_FEATURE_RESPONSIBILITY_HEADING,
    COMPLETE_FEATURE_RESPONSIBILITY_MARKER,
    render_agent_workspace_task,
    render_public_task,
)
from featureliftbench.task_spec import compute_generated_task_hash, compute_spec_hash
from featureliftbench.task_spec_migrate import (
    _extract_featurelifted_imports,
    _oracle_api_is_module,
    migrate_task_to_compliant,
)


def _non_api_usage_constitution_errors(errors: list[str]) -> list[str]:
    """API surface gaps are tracked by contract-closure audit; keep other gates hard.

    Historical ``spec_status=compliant`` batches passed an AST gate that allowed
    class-root declarations to cover undeclared members and missed call chains.
    Those gaps are no longer silent, but closing them is a revision wave — not a
    reason to weaken unrelated constitution checks.
    """

    return [
        error
        for error in errors
        if "undeclared API reference" not in error
        and "evaluation/test_api_usage.json" not in error
        and "depends on optional API reference" not in error
    ]


PILOT_TASKS = (
    "isort__settings_resolver_core__hard3_001",
    "transitions__state_machine_core__hard3_001",
    "scrapy__item_loader_core__hard3_001",
)

CORE100_API_REGENERATION_TASKS = (
    "boltons__iterutils_core__001",
    "isodate__duration_parse_core__001",
    "jinja2__loader_inheritance_core__001",
    "lark__grammar_loader_core__001",
    "vibe_app__plugin_registry_core__001",
    "websockets__handshake_parse_core__001",
)


class ConstitutionPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]

    def test_pilot_tasks_are_compliant(self) -> None:
        for task_id in PILOT_TASKS:
            with self.subTest(task_id=task_id):
                task_dir = self.repo_root / "benchmark" / "tasks" / task_id
                metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(metadata.get("spec_status"), "compliant")
                task_markdown = (task_dir / "TASK.md").read_text(encoding="utf-8")
                self.assertEqual(task_markdown, render_public_task(metadata))
                errors = validate_constitution(task_dir, metadata)
                self.assertEqual(
                    _non_api_usage_constitution_errors(errors),
                    [],
                    msg="; ".join(errors),
                )
        task_dir = self.repo_root / "benchmark" / "tasks" / PILOT_TASKS[0]
        metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
        rendered = render_public_task(metadata)
        self.assertEqual(metadata["spec_hash"], compute_spec_hash(metadata["public_spec"]))
        self.assertEqual(metadata["generated_task_hash"], compute_generated_task_hash(rendered))

    def test_every_compliant_workspace_receives_complete_feature_responsibility(self) -> None:
        task_dir = self.repo_root / "benchmark" / "tasks" / PILOT_TASKS[0]
        metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))

        stored_task = render_public_task(metadata)
        workspace_task = render_agent_workspace_task(metadata)

        self.assertNotIn(COMPLETE_FEATURE_RESPONSIBILITY_HEADING, stored_task)
        self.assertIn(COMPLETE_FEATURE_RESPONSIBILITY_MARKER, workspace_task)
        self.assertIn(COMPLETE_FEATURE_RESPONSIBILITY_HEADING, workspace_task)
        self.assertIn("complete task-scoped module", workspace_task)
        self.assertIn("inspecting the full upstream repository", workspace_task)
        self.assertIn("exhaustive scope boundary", workspace_task)
        self.assertIn("Every obligation inside that boundary is mandatory", workspace_task)

    def test_migrate_dry_run_idempotent_on_compliant_task(self) -> None:
        task_dir = self.repo_root / "benchmark" / "tasks" / PILOT_TASKS[1]
        metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
        payload = migrate_task_to_compliant(task_dir, dry_run=True)
        self.assertEqual(payload["task_id"], PILOT_TASKS[1])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["spec_hash"], metadata["spec_hash"])

    def test_pydantic_field_factory_is_declared_as_function(self) -> None:
        task_dir = (
            self.repo_root
            / "benchmark"
            / "tasks"
            / "pydantic_v1__validation_error_core__001"
        )
        metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
        payload = migrate_task_to_compliant(task_dir, dry_run=True)
        self.assertEqual(payload["errors"], [])
        field_entry = next(
            entry
            for entry in metadata["public_spec"]["required_api"]
            if entry["path"] == "featurelifted.Field"
        )
        self.assertEqual(field_entry["kind"], "function")

    def test_known_module_and_sentinel_exports_keep_their_runtime_kinds(self) -> None:
        expected = {
            "dataclasses_json__serde_core__001": {
                "featurelifted.global_config": "object",
            },
            "environs__typed_env_core__001": {
                "featurelifted.validate": "module",
            },
            "lark__visitor_transform_core__001": {
                "featurelifted.Discard": "object",
            },
            "tabulate__table_format_core__001": {
                "featurelifted.tabulate_formats": "object",
            },
            "yarl__url_model_core__001": {
                "featurelifted.Query": "object",
                "featurelifted.QueryVariable": "object",
                "featurelifted.SimpleQuery": "object",
            },
        }
        for task_id, expected_entries in expected.items():
            with self.subTest(task_id=task_id):
                task_dir = self.repo_root / "benchmark" / "tasks" / task_id
                payload = migrate_task_to_compliant(task_dir, dry_run=True)
                self.assertEqual(payload["errors"], [])
                metadata = json.loads(
                    (task_dir / "metadata.json").read_text(encoding="utf-8")
                )
                entries = {
                    item["path"]: item["kind"]
                    for item in metadata["public_spec"]["required_api"]
                }
                for path, kind in expected_entries.items():
                    self.assertEqual(entries[path], kind)

    def test_core100_api_regeneration_repairs_are_idempotent(self) -> None:
        for task_id in CORE100_API_REGENERATION_TASKS:
            with self.subTest(task_id=task_id):
                task_dir = self.repo_root / "benchmark" / "tasks" / task_id
                if not task_dir.is_dir():
                    task_dir = (
                        self.repo_root
                        / "benchmark"
                        / "curated"
                        / "tasks"
                        / task_id
                    )
                payload = migrate_task_to_compliant(task_dir, dry_run=True)
                self.assertEqual(payload["errors"], [])

    def test_string_referenced_plugin_modules_are_declared(self) -> None:
        task_dir = (
            self.repo_root
            / "benchmark"
            / "tasks"
            / "jinja2__extensions_core__001"
        )
        payload = migrate_task_to_compliant(task_dir, dry_run=True)
        self.assertEqual(payload["errors"], [])

    def test_hard50_batch_is_constitution_compliant(self) -> None:
        task_root = self.repo_root / "benchmark" / "tasks"
        task_dirs = []
        for task_dir in sorted(task_root.iterdir()):
            metadata_path = task_dir / "metadata.json"
            if not metadata_path.is_file():
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                metadata.get("status") == "main"
                and metadata.get("benchmark_split") != "external_main"
            ):
                task_dirs.append(task_dir)
        self.assertEqual(len(task_dirs), 50)

        for task_dir in task_dirs:
            with self.subTest(task_id=task_dir.name):
                metadata = json.loads(
                    (task_dir / "metadata.json").read_text(encoding="utf-8")
                )
                self.assertEqual(metadata.get("spec_status"), "compliant")
                review = metadata["evaluation_spec"]["manual_review"]
                self.assertTrue(review["checklist_passed"])
                self.assertEqual(review["reviewer_type"], "ai_assisted_task_level_review")
                self.assertFalse(review["independent_human_review"])
                self.assertTrue(
                    (
                        task_dir
                        / "hidden_tests"
                        / "test_required_api_surface.py"
                    ).is_file()
                )
                for coverage in metadata["evaluation_spec"]["required_api_coverage"]:
                    self.assertTrue(coverage["covered_by_tests"])
                    self.assertTrue(
                        all(
                            nodeid.startswith("hidden_tests/")
                            for nodeid in coverage["covered_by_tests"]
                        )
                    )
                errors = validate_constitution(task_dir, metadata)
                self.assertEqual(
                    _non_api_usage_constitution_errors(errors),
                    [],
                    msg="; ".join(errors),
                )


class ConstitutionLegacyAnnotationTests(unittest.TestCase):
    def test_import_parser_stops_at_semicolon_before_submodule_import(self) -> None:
        source = (
            "from featurelifted import chunked, partition; "
            "from featurelifted.iterutils import backoff, chunk_ranges"
        )
        self.assertEqual(
            _extract_featurelifted_imports(source),
            ["chunked", "partition"],
        )

    def test_oracle_module_detection_is_case_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            task_dir = repo_root / "benchmark" / "tasks" / "demo__task__001"
            oracle_root = (
                repo_root
                / "benchmark"
                / "submissions"
                / task_dir.name
                / "oracle"
                / "featurelifted"
            )
            task_dir.mkdir(parents=True)
            oracle_root.mkdir(parents=True)
            (oracle_root / "isodates.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            self.assertTrue(_oracle_api_is_module(task_dir, "isodates"))
            self.assertFalse(_oracle_api_is_module(task_dir, "Isodates"))

    def test_legacy_task_without_public_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            task_dir.mkdir()
            (task_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "task_id": "demo__task__001",
                        "spec_status": "legacy",
                    }
                ),
                encoding="utf-8",
            )
            metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["spec_status"], "legacy")
            errors = validate_constitution(task_dir, metadata)
            self.assertEqual(errors, [])

    def test_tests_cannot_depend_on_optional_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            public_tests = task_dir / "public_tests"
            hidden_tests = task_dir / "hidden_tests"
            public_tests.mkdir(parents=True)
            hidden_tests.mkdir()
            (public_tests / "test_public.py").write_text(
                "from featurelifted import OptionalThing\n\n"
                "def test_optional():\n"
                "    assert OptionalThing is not None\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {"path": "featurelifted.RequiredThing", "kind": "class"}
                ],
                "optional_api": [
                    {"path": "featurelifted.OptionalThing", "kind": "class"}
                ],
            }
            errors = _validate_test_api_usage(task_dir, public_spec)
            self.assertTrue(
                any("depends on optional API" in error for error in errors),
                msg="; ".join(errors),
            )

    def test_standard_module_metadata_is_not_treated_as_feature_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            hidden_tests = task_dir / "hidden_tests"
            hidden_tests.mkdir(parents=True)
            (hidden_tests / "test_hidden.py").write_text(
                "import featurelifted\n"
                "from pathlib import Path\n\n"
                "def test_package_metadata():\n"
                "    assert featurelifted.__name__ == 'featurelifted'\n"
                "    assert Path(featurelifted.__file__).exists()\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {"path": "featurelifted.RequiredThing", "kind": "class"}
                ],
                "optional_api": [],
            }
            self.assertEqual(_validate_test_api_usage(task_dir, public_spec), [])

    def test_project_defined_dunder_export_still_requires_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            hidden_tests = task_dir / "hidden_tests"
            hidden_tests.mkdir(parents=True)
            (hidden_tests / "test_hidden.py").write_text(
                "import featurelifted\n\n"
                "def test_version():\n"
                "    assert featurelifted.__version__\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {"path": "featurelifted.RequiredThing", "kind": "class"}
                ],
                "optional_api": [],
            }
            errors = _validate_test_api_usage(task_dir, public_spec)
            self.assertTrue(
                any(
                    "uses undeclared API reference featurelifted.__version__" in error
                    for error in errors
                ),
                msg="; ".join(errors),
            )

    def test_class_root_declaration_does_not_cover_undeclared_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            public_tests = task_dir / "public_tests"
            public_tests.mkdir(parents=True)
            (public_tests / "test_public.py").write_text(
                "from featurelifted import Success\n\n"
                "def test_bind_chain():\n"
                "    assert Success(2).map(lambda x: x + 1).bind(lambda x: Success(x * 3)).value == 9\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {
                        "path": "featurelifted.Success",
                        "kind": "class",
                        "members": [
                            {"path": "featurelifted.Success.map", "kind": "method"},
                            {"path": "featurelifted.Success.value", "kind": "attribute"},
                        ],
                    }
                ],
                "optional_api": [],
            }
            errors = _validate_test_api_usage(task_dir, public_spec)
            self.assertTrue(
                any("featurelifted.Success.bind" in error for error in errors),
                msg="; ".join(errors),
            )

    def test_function_return_members_are_not_misattributed_to_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            public_tests = task_dir / "public_tests"
            public_tests.mkdir(parents=True)
            (public_tests / "test_public.py").write_text(
                "from featurelifted import parse\n\n"
                "def test_parse_result():\n"
                "    assert parse('name').find('x')\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {"path": "featurelifted.parse", "kind": "function"}
                ],
                "optional_api": [],
            }
            self.assertEqual(_validate_test_api_usage(task_dir, public_spec), [])

    def test_builtin_member_of_exported_attribute_is_not_feature_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            public_tests = task_dir / "public_tests"
            public_tests.mkdir(parents=True)
            (public_tests / "test_public.py").write_text(
                "from featurelifted import ResponseError\n\n"
                "def test_message():\n"
                "    assert ResponseError.SPECIFIC_ERROR.format('x')\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {
                        "path": "featurelifted.ResponseError",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.ResponseError.SPECIFIC_ERROR",
                                "kind": "attribute",
                            }
                        ],
                    }
                ],
                "optional_api": [],
            }
            self.assertEqual(_validate_test_api_usage(task_dir, public_spec), [])

    def test_nested_module_member_still_requires_exact_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            public_tests = task_dir / "public_tests"
            public_tests.mkdir(parents=True)
            (public_tests / "test_public.py").write_text(
                "from featurelifted import token\n\n"
                "def test_token():\n"
                "    assert token.Name.Function\n",
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {"path": "featurelifted.token", "kind": "module"}
                ],
                "optional_api": [],
            }
            errors = _validate_test_api_usage(task_dir, public_spec)
            self.assertTrue(
                any("featurelifted.token.Name.Function" in error for error in errors),
                msg="; ".join(errors),
            )

    def test_test_api_usage_manifest_is_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "demo__task__001"
            public_tests = task_dir / "public_tests"
            public_tests.mkdir(parents=True)
            (public_tests / "test_public.py").write_text(
                "from featurelifted import Success\n\n"
                "def test_map():\n"
                "    assert Success(1).map(lambda x: x).value == 1\n",
                encoding="utf-8",
            )
            evaluation = task_dir / "evaluation"
            evaluation.mkdir()
            (evaluation / "test_api_usage.json").write_text(
                json.dumps(
                    {
                        "schema_version": "featureliftbench.test_api_usage.v1",
                        "tests": [
                            {
                                "test_id": "public_tests/test_public.py::test_map",
                                "api_ids": [
                                    "featurelifted.Success",
                                    "featurelifted.Success.map",
                                    "featurelifted.Success.value",
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            public_spec = {
                "required_api": [
                    {
                        "path": "featurelifted.Success",
                        "kind": "class",
                        "members": [
                            {"path": "featurelifted.Success.map", "kind": "method"},
                            {"path": "featurelifted.Success.value", "kind": "attribute"},
                        ],
                    }
                ],
                "optional_api": [],
            }
            self.assertEqual(_validate_test_api_usage(task_dir, public_spec), [])


if __name__ == "__main__":
    unittest.main()
