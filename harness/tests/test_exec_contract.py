"""Unit tests for Execution-Guided Contract helpers."""

from __future__ import annotations

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.exec_contract.audit import compute_contract_gate_ok
from featureliftbench.exec_contract.audit import compute_evidence_gate_ok
from featureliftbench.exec_contract.audit import evidence_gate_failures
from featureliftbench.exec_contract.common import keywords_from_public_spec
from featureliftbench.exec_contract.runtime_doctor import build_runtime_plan
from featureliftbench.exec_contract.select_tests import select_upstream_tests
from featureliftbench.exec_contract.synthesize import infer_api_from_upstream
from featureliftbench.exec_contract.synthesize import synthesize_contracts
from featureliftbench.exec_contract.workspace import install_exec_contract_workspace
from featureliftbench.metadata import load_metadata


class ExecContractAblationTests(unittest.TestCase):
    def test_arm_name(self) -> None:
        self.assertEqual(
            AblationOptions(exec_contract=True).ablation_arm, "exec_contract"
        )
        self.assertEqual(
            AblationOptions(
                exec_contract=True, exec_contract_variant="cgcc_lite"
            ).ablation_arm,
            "cgcc_lite",
        )
        self.assertEqual(
            AblationOptions(
                exec_contract=True, exec_contract_variant="cgcc_roc"
            ).ablation_arm,
            "cgcc_roc",
        )
        self.assertEqual(
            AblationOptions(
                exec_contract=True, exec_contract_variant="cgcc_rmc"
            ).ablation_arm,
            "cgcc_rmc",
        )
        self.assertEqual(
            AblationOptions(
                exec_contract=True, exec_contract_variant="fcec"
            ).ablation_arm,
            "fcec",
        )

    def test_mutually_exclusive_with_td(self) -> None:
        with self.assertRaises(ValueError):
            AblationOptions(td_cognition=True, exec_contract=True)

    def test_resolve_from_profile(self) -> None:
        options = resolve_ablation_options(
            profile={
                "exec_contract": True,
                "exec_contract_variant": "cgcc_lite",
            }
        )
        self.assertTrue(options.exec_contract)
        self.assertEqual(options.exec_contract_variant, "cgcc_lite")
        self.assertEqual(options.ablation_arm, "cgcc_lite")


class ExecContractSelectSynthesizeTests(unittest.TestCase):
    def test_keywords_strip_stopwords(self) -> None:
        keys = keywords_from_public_spec(
            {
                "title": "LazyCommandCollection",
                "required_api": [
                    {
                        "path": "featurelifted.LazyCommandCollection",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.LazyCommandCollection.resolve",
                                "kind": "method",
                            }
                        ],
                    }
                ],
                "behaviors": [
                    {
                        "id": "B001",
                        "text": "When a command name is requested, the package returns it.",
                    }
                ],
            }
        )
        self.assertIn("lazycommandcollection", keys)
        self.assertNotIn("when", keys)
        self.assertNotIn("the", keys)
        self.assertNotIn("api", keys)

    def test_select_demotes_db_backends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            tests = repo / "tests"
            tests.mkdir(parents=True)
            (tests / "test_revision.py").write_text(
                "def test_revision_map():\n    assert True\n",
                encoding="utf-8",
            )
            (tests / "test_mysql.py").write_text(
                "def test_mysql_revision():\n    assert True\n",
                encoding="utf-8",
            )
            public_spec = {
                "title": "RevisionMap",
                "source_entrypoints": ["alembic.ddl.RevisionMap"],
                "required_api": [
                    {"path": "featurelifted.RevisionMap", "kind": "class"}
                ],
            }
            selected = select_upstream_tests(repo, public_spec, max_files=2)
            self.assertTrue(any("revision" in s for s in selected))
            self.assertFalse(any("mysql" in s for s in selected))

    def test_select_demotes_benchmark_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "benchmarks").mkdir()
            (repo / "tests" / "test_result").mkdir(parents=True)
            (repo / "benchmarks" / "test_benchmarks.py").write_text(
                "from returns.result import Success\n"
                "def test_every_result_method():\n"
                "    assert Success(1).map(lambda x: x)\n" * 20,
                encoding="utf-8",
            )
            focused = repo / "tests" / "test_result" / "test_result_map.py"
            focused.write_text(
                "from returns.result import Success\n"
                "def test_result_map():\n"
                "    assert Success(1).map(lambda x: x)\n",
                encoding="utf-8",
            )
            selected = select_upstream_tests(
                repo,
                {
                    "title": "Result Success Failure safe",
                    "source_entrypoints": ["returns.result.Success"],
                    "behaviors": [
                        {"id": "B001", "text": "Success map transforms a value."}
                    ],
                },
            )
            self.assertEqual(selected, ["tests/test_result/test_result_map.py"])

    def test_runtime_doctor_reads_nearest_project_test_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            nested = repo / "package"
            (nested / "tests").mkdir(parents=True)
            (nested / "tests" / "test_core.py").write_text(
                "def test_core(): pass\n",
                encoding="utf-8",
            )
            (nested / "pyproject.toml").write_text(
                textwrap.dedent(
                    """
                    [project]
                    name = "demo"
                    version = "1"

                    [dependency-groups]
                    test = ["pytest-timeout", {include-group = "shared"}]
                    shared = ["packaging"]

                    [tool.pytest.ini_options]
                    minversion = "8.2"
                    """
                ),
                encoding="utf-8",
            )
            plan = build_runtime_plan(
                repo,
                ["package/tests/test_core.py"],
            )
            self.assertEqual(plan["project_root"], "package")
            self.assertIn("pytest-timeout", plan["test_requirements"])
            self.assertIn("packaging", plan["test_requirements"])
            self.assertIn("pytest>=8.2", plan["test_requirements"])

    def test_infer_invoke_from_upstream_ast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "click"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "core.py").write_text(
                textwrap.dedent(
                    """
                    class Context:
                        default_map = None
                        auto_envvar_prefix = None

                    class LazyCommandCollection:
                        def __init__(self, sources, envvar=None):
                            pass
                        def get_command(self, name):
                            pass
                        def resolve(self, argv):
                            pass
                        def invoke(self, args):
                            pass
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            public_spec = {
                "title": "LazyCommandCollection",
                "source_entrypoints": ["click.core.LazyCommandCollection"],
                "required_api": [
                    {
                        "path": "featurelifted.LazyCommandCollection",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.LazyCommandCollection.resolve",
                                "kind": "method",
                            }
                        ],
                    }
                ],
            }
            inferred = infer_api_from_upstream(root, public_spec)
            self.assertIn("invoke", inferred["methods"])
            paths = {a["path"] for a in inferred["api"]}
            self.assertIn("featurelifted.LazyCommandCollection.invoke", paths)

    def test_infer_lazy_alias_and_inherited_invoke(self) -> None:
        """Frozen click may only have CommandCollection; invoke lives on Group."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "click"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "core.py").write_text(
                textwrap.dedent(
                    """
                    class Context:
                        default_map = None

                    class Command:
                        def invoke(self, ctx):
                            return "ok"

                    class Group(Command):
                        def get_command(self, ctx, name):
                            pass

                    class CommandCollection(Group):
                        def list_commands(self, ctx):
                            return []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            public_spec = {
                "title": "LazyCommandCollection",
                "source_entrypoints": ["click.core.LazyCommandCollection"],
                "required_api": [
                    {
                        "path": "featurelifted.LazyCommandCollection",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.LazyCommandCollection.get_command",
                                "kind": "method",
                            }
                        ],
                    }
                ],
            }
            inferred = infer_api_from_upstream(root, public_spec)
            self.assertIn("invoke", inferred["methods"])
            self.assertIn("get_command", inferred["methods"])
            paths = {a["path"] for a in inferred["api"]}
            self.assertIn("featurelifted.LazyCommandCollection.invoke", paths)
            self.assertIn("featurelifted.LazyCommandCollection.get_command", paths)

    def test_synthesize_scenarios_not_assert_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            tests = repo / "tests"
            tests.mkdir(parents=True)
            (tests / "test_evict.py").write_text(
                "def test_evict():\n    assert True\n",
                encoding="utf-8",
            )
            click = repo / "click"
            click.mkdir()
            (click / "__init__.py").write_text("", encoding="utf-8")
            (click / "core.py").write_text(
                textwrap.dedent(
                    """
                    class Context:
                        default_map = None

                    class LazyCommandCollection:
                        def get_command(self, name):
                            pass
                        def resolve(self, argv):
                            pass
                        def invoke(self, args):
                            pass
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            public_spec = {
                "title": "LazyCommandCollection",
                "source_entrypoints": ["click.core.LazyCommandCollection"],
                "required_api": [
                    {
                        "path": "featurelifted.LazyCommandCollection",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.LazyCommandCollection.get_command",
                                "kind": "method",
                            },
                            {
                                "path": "featurelifted.LazyCommandCollection.resolve",
                                "kind": "method",
                            },
                        ],
                    },
                    {"path": "featurelifted.Command", "kind": "class"},
                ],
                "behaviors": [
                    {
                        "id": "B002",
                        "text": "When a context is created, envvar settings are propagated.",
                    }
                ],
            }
            install_exec_contract_workspace(root)
            (root / "runtime_traces").mkdir(exist_ok=True)
            (root / "runtime_traces" / "traces.jsonl").write_text("", encoding="utf-8")
            meta = synthesize_contracts(
                root, public_spec, collect_meta={"trace_quality": "low"}
            )
            self.assertTrue(meta["contracts_substantive"])
            self.assertGreaterEqual(meta["scenario_assertions"], 2)
            scenario = (root / "contracts" / "test_behavior_scenarios.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("invoke", scenario)
            self.assertIn("test_invoke_runs_callback_over_argv", scenario)
            self.assertIn("test_resolve_returns_context_command_and_remaining_argv", scenario)
            self.assertIn("FLB_FEATURE_DEFAULTS", scenario)
            surface = (root / "contracts" / "test_required_surface.py").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("format_help", surface)
            # Must NOT leak benchmark failure strings / eval graphs.
            self.assertNotIn("no such command", scenario)
            self.assertNotIn("feature_tip", scenario)
            self.assertNotIn("FLB_CLICK_DEFAULTS", scenario)
            self.assertNotIn("assert True", scenario)
            checklist = (root / "contracts" / "test_behavior_checklist.py").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("assert True", checklist)

    def test_fcec_capsule_binds_trace_to_clause_and_checks_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo" / "demo").mkdir(parents=True)
            (root / "repo" / "demo" / "__init__.py").write_text(
                "", encoding="utf-8"
            )
            install_exec_contract_workspace(root)
            event = {
                "func": "register",
                "file": "/runtime/demo/actions.py",
                "args": {"name": "alpha"},
                "return": None,
                "event": "call",
            }
            (root / "runtime_traces" / "traces.jsonl").write_text(
                json.dumps(event) + "\n",
                encoding="utf-8",
            )
            spec = {
                "required_api": [
                    {
                        "path": "featurelifted.Registry",
                        "kind": "class",
                        "signature": "() -> 'None'",
                        "members": [
                            {
                                "path": "featurelifted.Registry.register",
                                "kind": "method",
                                "signature": "(self, name: 'str', strict: 'bool' = False) -> 'None'",
                            }
                        ],
                    }
                ],
                "behaviors": [
                    {
                        "id": "B001",
                        "text": "`register` records a name.",
                    }
                ],
            }
            meta = synthesize_contracts(
                root,
                spec,
                collect_meta={
                    "trace_quality": "high",
                    "selected_tests": ["tests/test_actions.py"],
                },
                variant="fcec",
            )
            capsule = json.loads(
                (root / "CLOSURE_CAPSULE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(meta["clause_bound_obligations"], 1)
            self.assertEqual(meta["behavior_replay_cases"], 0)
            self.assertFalse(meta["contracts_substantive"])
            self.assertEqual(
                capsule["dynamic_bindings"][0]["behavior_id"],
                "B001",
            )
            surface = (
                root / "contracts" / "test_required_surface.py"
            ).read_text(encoding="utf-8")
            self.assertIn("test_signature_featurelifted_Registry_register", surface)

    def test_fcec_allows_state_free_top_level_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            install_exec_contract_workspace(root)
            (root / "runtime_traces" / "traces.jsonl").write_text(
                json.dumps(
                    {
                        "func": "normalize",
                        "file": "/runtime/demo.py",
                        "args": {"value": 1},
                        "return": 2,
                        "event": "call",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            spec = {
                "required_api": [
                    {
                        "path": "featurelifted.normalize",
                        "kind": "function",
                        "signature": "(value: 'int') -> 'int'",
                    }
                ],
                "behaviors": [
                    {"id": "B001", "text": "`normalize` transforms a value."}
                ],
            }
            meta = synthesize_contracts(
                root,
                spec,
                collect_meta={
                    "trace_quality": "high",
                    "selected_tests": ["tests/test_demo.py"],
                },
                variant="fcec",
            )
            self.assertEqual(meta["behavior_replay_cases"], 1)
            self.assertTrue(meta["contracts_substantive"])

    def test_synthesize_alembic_eval_blind_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            (repo / "tests").mkdir(parents=True)
            (repo / "tests" / "test_revision.py").write_text(
                "def test_revision():\n    assert True\n", encoding="utf-8"
            )
            alembic = repo / "alembic" / "script"
            alembic.mkdir(parents=True)
            (repo / "alembic" / "__init__.py").write_text("", encoding="utf-8")
            (alembic / "__init__.py").write_text("", encoding="utf-8")
            (alembic / "revision.py").write_text(
                textwrap.dedent(
                    """
                    class Revision:
                        pass

                    class RevisionMap:
                        # Ordering required: upstream uses OrderedDict / OrderedSet.
                        def get_revision(self, id_):
                            pass
                        def get_heads(self):
                            pass
                        def ancestors(self, revision_id, include_dependencies=True):
                            pass
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            public_spec = {
                "title": "RevisionMap",
                "source_entrypoints": ["alembic.script.revision.RevisionMap"],
                "required_api": [
                    {
                        "path": "featurelifted.RevisionMap",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.RevisionMap.get_revision",
                                "kind": "method",
                            },
                            {
                                "path": "featurelifted.RevisionMap.ancestors",
                                "kind": "method",
                            },
                        ],
                    },
                    {"path": "featurelifted.Revision", "kind": "class"},
                    {"path": "featurelifted.MissingRevision", "kind": "exception"},
                ],
                "behaviors": [
                    {
                        "id": "B006",
                        "text": "When symbolic identifiers such as head or base are requested, resolve them.",
                    }
                ],
            }
            install_exec_contract_workspace(root)
            (root / "runtime_traces").mkdir(exist_ok=True)
            (root / "runtime_traces" / "traces.jsonl").write_text("", encoding="utf-8")
            meta = synthesize_contracts(
                root, public_spec, collect_meta={"trace_quality": "medium"}
            )
            self.assertTrue(meta["contracts_substantive"])
            self.assertGreaterEqual(meta["scenario_assertions"], 2)
            scenario = (root / "contracts" / "test_behavior_scenarios.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("MissingRevision", scenario)
            self.assertIn("test_ancestors_excludes_self_on_linear_chain", scenario)
            self.assertIn("test_revision_down_revision_defaults_to_none", scenario)
            self.assertIn("test_merge_graph_heads_and_branch_point", scenario)
            self.assertNotIn("test_symbolic_fallback_preserves_registered_identifier", scenario)
            # Leaky eval-graph scenarios must be gone.
            self.assertNotIn("test_heads_order_with_dependency_branch", scenario)
            self.assertNotIn("feature_tip", scenario)
            self.assertNotIn("test_literal_revision_id_base", scenario)
            self.assertNotIn("assert True", scenario)

            cgcc_meta = synthesize_contracts(
                root,
                public_spec,
                collect_meta={"trace_quality": "medium"},
                variant="cgcc_lite",
            )
            self.assertEqual(cgcc_meta["contract_variant"], "cgcc_lite")
            self.assertTrue(cgcc_meta["mutation_adequacy_ok"])
            self.assertIn(
                "symbol_overgeneralization",
                cgcc_meta["covered_mutation_families"],
            )
            cgcc_scenario = (
                root / "contracts" / "test_behavior_scenarios.py"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "test_symbolic_fallback_preserves_registered_identifier",
                cgcc_scenario,
            )
            self.assertIn(
                "test_independent_heads_preserve_source_order",
                cgcc_scenario,
            )
            self.assertNotIn("feature_tip", cgcc_scenario)
            obligations = json.loads(
                (root / "OBLIGATIONS.json").read_text(encoding="utf-8")
            )
            audit = json.loads(
                (root / "MUTATION_AUDIT.json").read_text(encoding="utf-8")
            )
            self.assertTrue(obligations["obligations"])
            self.assertTrue(audit["mutation_adequacy_ok"])

    def test_cgcc_click_contrasts_requested_and_unrequested_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            click = repo / "click"
            click.mkdir(parents=True)
            (click / "__init__.py").write_text("", encoding="utf-8")
            (click / "core.py").write_text(
                textwrap.dedent(
                    """
                    class Context:
                        default_map = None

                    class LazyCommandCollection:
                        def get_command(self, name):
                            pass
                        def resolve(self, argv):
                            pass
                        def invoke(self, args):
                            pass
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            public_spec = {
                "title": "LazyCommandCollection",
                "source_entrypoints": ["click.core.LazyCommandCollection"],
                "required_api": [
                    {
                        "path": "featurelifted.LazyCommandCollection",
                        "kind": "class",
                        "members": [
                            {
                                "path": "featurelifted.LazyCommandCollection.get_command",
                                "kind": "method",
                            },
                            {
                                "path": "featurelifted.LazyCommandCollection.resolve",
                                "kind": "method",
                            },
                        ],
                    },
                    {"path": "featurelifted.Command", "kind": "class"},
                    {"path": "featurelifted.UsageError", "kind": "exception"},
                ],
                "behaviors": [
                    {
                        "id": "B001",
                        "text": "Loads only the requested source and caches the command.",
                    },
                    {
                        "id": "B002",
                        "text": "Envvar defaults propagate into the context default_map.",
                    },
                    {
                        "id": "B003",
                        "text": "Resolve returns command context and raises UsageError.",
                    },
                ],
            }
            install_exec_contract_workspace(root)
            (root / "runtime_traces" / "traces.jsonl").write_text(
                "", encoding="utf-8"
            )
            meta = synthesize_contracts(
                root,
                public_spec,
                collect_meta={"trace_quality": "low"},
                variant="cgcc_lite",
            )
            scenario = (
                root / "contracts" / "test_behavior_scenarios.py"
            ).read_text(encoding="utf-8")
            self.assertIn("test_get_command_is_selective_and_cached", scenario)
            self.assertIn("'other': 0", scenario)
            self.assertIn("api_member_deletion", meta["covered_mutation_families"])
            self.assertIn("lazy_state_collapse", meta["covered_mutation_families"])
            self.assertTrue(meta["mutation_adequacy_ok"])

    def test_cgcc_real_focus_tasks_have_expected_eval_blind_families(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        expected = {
            "alembic__revision_map_core__hard3_001": {
                "symbol_overgeneralization",
                "ordered_output_collapse",
                "edge_role_collapse",
            },
            "click__lazy_command_core__hard3_001": {
                "api_member_deletion",
                "lazy_state_collapse",
                "context_propagation_omission",
            },
        }
        for task_id, required_families in expected.items():
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as tmp:
                task_dir = repo_root / "benchmark" / "tasks" / task_id
                root = Path(tmp)
                shutil.copytree(task_dir / "repo", root / "repo")
                install_exec_contract_workspace(root)
                (root / "runtime_traces" / "traces.jsonl").write_text(
                    "", encoding="utf-8"
                )
                public_spec = load_metadata(task_dir).data["public_spec"]
                meta = synthesize_contracts(
                    root,
                    public_spec,
                    collect_meta={"trace_quality": "low"},
                    variant="cgcc_lite",
                )
                self.assertTrue(meta["mutation_adequacy_ok"])
                self.assertTrue(
                    required_families.issubset(
                        set(meta["covered_mutation_families"])
                    )
                )

    def test_cgcc_roc_separates_branch_alias_origin_from_propagation(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        task_dir = (
            repo_root
            / "benchmark"
            / "tasks"
            / "alembic__revision_map_core__hard3_001"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(task_dir / "repo", root / "repo")
            install_exec_contract_workspace(root)
            (root / "runtime_traces" / "traces.jsonl").write_text(
                "", encoding="utf-8"
            )
            public_spec = load_metadata(task_dir).data["public_spec"]
            meta = synthesize_contracts(
                root,
                public_spec,
                collect_meta={"trace_quality": "low"},
                variant="cgcc_roc",
            )
            scenario = (
                root / "contracts" / "test_behavior_scenarios.py"
            ).read_text(encoding="utf-8")
            self.assertEqual(meta["contract_variant"], "cgcc_roc")
            self.assertIn(
                "observable_representation_collapse",
                meta["covered_mutation_families"],
            )
            self.assertIn(
                "test_branch_label_binding_is_distinct_from_propagated_head",
                scenario,
            )
            self.assertIn(
                "revmap.branch_labels.get('stable') == 'origin'",
                scenario,
            )

    def test_cgcc_rmc_adds_required_revision_method_witnesses(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        task_dir = (
            repo_root
            / "benchmark"
            / "tasks"
            / "alembic__revision_map_core__hard3_001"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(task_dir / "repo", root / "repo")
            install_exec_contract_workspace(root)
            (root / "runtime_traces" / "traces.jsonl").write_text(
                "", encoding="utf-8"
            )
            public_spec = load_metadata(task_dir).data["public_spec"]
            meta = synthesize_contracts(
                root,
                public_spec,
                collect_meta={"trace_quality": "low"},
                variant="cgcc_rmc",
            )
            scenario = (
                root / "contracts" / "test_behavior_scenarios.py"
            ).read_text(encoding="utf-8")
            self.assertEqual(meta["contract_variant"], "cgcc_rmc")
            self.assertIn(
                "required_method_behavior_omission",
                meta["covered_mutation_families"],
            )
            self.assertIn(
                "test_iterate_revisions_excludes_lower_by_default",
                scenario,
            )
            self.assertIn(
                "test_get_revisions_preserves_requested_identifier_order",
                scenario,
            )

    def test_gate_rejects_vacuous_green(self) -> None:
        self.assertFalse(
            compute_contract_gate_ok(
                collect_meta={"trace_quality": "medium"},
                synthesize_meta={"contracts_substantive": False, "scenario_assertions": 0},
                verify_final={"ok": True},
            )
        )

    def test_fcec_evidence_gate_is_fail_closed(self) -> None:
        collect = {
            "collector_returncode": 0,
            "pytest_passed": True,
            "useful_trace_events": 3,
            "trace_quality": "high",
        }
        synthesize = {
            "contract_variant": "fcec",
            "contracts_substantive": True,
            "scenario_assertions": 3,
            "api_closure_complete": True,
            "signature_closure_complete": True,
            "clause_bound_obligations": 1,
        }
        self.assertTrue(
            compute_evidence_gate_ok(
                collect_meta=collect,
                synthesize_meta=synthesize,
            )
        )
        missing_trace = {**collect, "useful_trace_events": 0}
        self.assertFalse(
            compute_evidence_gate_ok(
                collect_meta=missing_trace,
                synthesize_meta=synthesize,
            )
        )
        self.assertIn(
            "no relevant upstream trace event",
            evidence_gate_failures(
                collect_meta=missing_trace,
                synthesize_meta=synthesize,
            ),
        )
        self.assertFalse(
            compute_contract_gate_ok(
                collect_meta=missing_trace,
                synthesize_meta=synthesize,
                verify_final={"ok": True, "stdout_tail": "6 passed"},
            )
        )

    def test_cgcc_gate_requires_mutation_adequacy(self) -> None:
        self.assertFalse(
            compute_contract_gate_ok(
                collect_meta={"trace_quality": "medium"},
                synthesize_meta={
                    "contract_variant": "cgcc_lite",
                    "contracts_substantive": True,
                    "scenario_assertions": 4,
                    "mutation_adequacy_ok": False,
                },
                verify_final={
                    "ok": True,
                    "stdout_tail": "8 passed, 1 skipped",
                },
            )
        )
        self.assertFalse(
            compute_contract_gate_ok(
                collect_meta={"trace_quality": "medium"},
                synthesize_meta={"contracts_substantive": True, "scenario_assertions": 1},
                verify_final={"ok": True},
            )
        )
        self.assertTrue(
            compute_contract_gate_ok(
                collect_meta={"trace_quality": "medium"},
                synthesize_meta={"contracts_substantive": True, "scenario_assertions": 2},
                verify_final={"ok": True, "stdout_tail": "5 passed in 0.01s"},
            )
        )
        self.assertFalse(
            compute_contract_gate_ok(
                collect_meta={"trace_quality": "medium"},
                synthesize_meta={"contracts_substantive": True, "scenario_assertions": 2},
                verify_final={"ok": True, "stdout_tail": "3 passed, 9 skipped in 0.01s"},
            )
        )


if __name__ == "__main__":
    unittest.main()
