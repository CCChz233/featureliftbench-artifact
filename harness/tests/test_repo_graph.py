from __future__ import annotations

import contextlib
import io
import importlib.metadata
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from featureliftbench.repo_graph.builder import GraphBuilder
from featureliftbench.repo_graph.cli import main as graph_cli
from featureliftbench.repo_graph.protocol import dumps_response, response_payload
from featureliftbench.repo_graph.query import GraphQueryEngine
from featureliftbench.repo_graph.parsing import TreeSitterBackend
from featureliftbench.repo_graph.policy import BOOTSTRAP_MAX_CHARS_ENV, CACHE_DIR_ENV, MODE_ENV, ROOT_ENV
from featureliftbench.repo_graph.ledger import RepoGraphLedger
from featureliftbench.repo_graph.runtime import append_repo_graph_prompt, finalize_repo_graph, initialize_repo_graph
from featureliftbench.repo_graph.storage import JsonlGraphStore
from featureliftbench.repo_graph.submission import compare_submission, sync_submission


PYTHON_SOURCE = """\
import os
from pathlib import Path

STATE = []

def helper(value):
    return value + 1

class Service(BaseService):
    @classmethod
    def run(cls, value):
        return helper(value)

def configured():
    return os.getenv("FEATURE_MODE")

def directly_configured():
    return os.environ["DIRECT_MODE"]

def resource_path():
    return Path(__file__).parent / "schema.json"
"""

GO_SOURCE = """\
package calc

import "fmt"

type Runner interface {
    Run()
}

type Service struct{}

func (s *Service) Run() {}

func Add(a int, b int) int {
    fmt.Println(a)
    return a + b
}
"""


class RepositoryGraphTests(unittest.TestCase):
    def _repository(self, root: Path, name: str = "source-repo") -> Path:
        repository = root / name
        (repository / "pkg").mkdir(parents=True)
        (repository / "gopkg").mkdir(parents=True)
        (repository / "pkg" / "core.py").write_text(PYTHON_SOURCE, encoding="utf-8")
        (repository / "gopkg" / "add.go").write_text(GO_SOURCE, encoding="utf-8")
        return repository

    def test_builds_shared_ir_for_python_and_go(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self._repository(Path(temporary))
            snapshot = GraphBuilder().build(repository)

        by_stable_id = {node.stable_id: node for node in snapshot.nodes}
        self.assertIn("python:pkg.core.helper:function", by_stable_id)
        self.assertIn("python:pkg.core.Service.run:method", by_stable_id)
        self.assertIn("python:pkg.core.STATE:global_state", by_stable_id)
        self.assertIn("go:gopkg.calc.Add:function", by_stable_id)
        self.assertIn("go:gopkg.calc.Runner:interface", by_stable_id)
        self.assertIn("go:gopkg.calc.Runner.Run:interface_method", by_stable_id)
        self.assertIn("go:gopkg.calc.Service.Run:method", by_stable_id)
        self.assertEqual(snapshot.manifest["counts"]["languages"], {"go": 1, "python": 1})
        self.assertEqual(snapshot.manifest["counts"]["parse_error_files"], 0)
        self.assertRegex(snapshot.manifest["builder"]["implementation_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(snapshot.manifest["builder"]["adapters"]["python"]["grammar"]["abi_version"], 15)

        helper_id = by_stable_id["python:pkg.core.helper:function"].id
        call_edges = [edge for edge in snapshot.edges if edge.kind == "CALLS" and edge.target == helper_id]
        self.assertEqual(len(call_edges), 1)
        self.assertIn(call_edges[0].resolution, {"exact", "probable"})

        env_edges = [edge for edge in snapshot.edges if edge.kind == "READS_ENV"]
        self.assertEqual(len(env_edges), 2)
        self.assertTrue(all(edge.resolution == "exact" for edge in env_edges))

    def test_snapshot_identity_and_graph_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self._repository(Path(temporary))
            first = GraphBuilder().build(repository)
            second = GraphBuilder().build(repository)

        self.assertEqual(first.manifest["snapshot_id"], second.manifest["snapshot_id"])
        self.assertEqual(first.manifest["graph_hash"], second.manifest["graph_hash"])
        self.assertEqual(
            [node.to_dict() for node in first.nodes],
            [node.to_dict() for node in second.nodes],
        )
        self.assertEqual(
            [edge.to_dict() for edge in first.edges],
            [edge.to_dict() for edge in second.edges],
        )

    def test_preparse_fingerprint_matches_built_snapshot_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self._repository(Path(temporary))
            builder = GraphBuilder()
            fingerprint = builder.fingerprint(repository)
            snapshot = builder.build(repository)
        self.assertEqual(fingerprint["snapshot_id"], snapshot.manifest["snapshot_id"])
        self.assertEqual(fingerprint["source_tree_hash"], snapshot.manifest["source"]["tree_hash"])

    def test_non_code_resource_changes_snapshot_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self._repository(Path(temporary))
            resource = repository / "pkg" / "schema.json"
            resource.write_text('{"version": 1}', encoding="utf-8")
            first = GraphBuilder().build(repository)
            resource.write_text('{"version": 2}', encoding="utf-8")
            second = GraphBuilder().build(repository)
        self.assertNotEqual(first.manifest["snapshot_id"], second.manifest["snapshot_id"])
        self.assertEqual(first.manifest["graph_hash"], second.manifest["graph_hash"])

    def test_mount_directory_name_does_not_change_graph_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_repo = self._repository(root, "first-mount")
            second_repo = self._repository(root, "second-mount")
            first = GraphBuilder().build(first_repo)
            second = GraphBuilder().build(second_repo)
        self.assertEqual(first.manifest["snapshot_id"], second.manifest["snapshot_id"])
        self.assertEqual(first.manifest["graph_hash"], second.manifest["graph_hash"])

    def test_jsonl_store_round_trip_and_path_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            graph_dir = root / "graph"
            snapshot = GraphBuilder().build(repository)
            store = JsonlGraphStore()
            store.write(snapshot, graph_dir)
            loaded = store.load(graph_dir)
            serialized = "".join(
                (graph_dir / name).read_text(encoding="utf-8")
                for name in ("manifest.json", "nodes.jsonl", "edges.jsonl")
            )

        self.assertEqual(loaded.manifest["graph_hash"], snapshot.manifest["graph_hash"])
        self.assertNotIn(str(repository), serialized)
        self.assertEqual(JsonlGraphStore().check(loaded), [])

    def test_search_bootstrap_closure_and_risks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = GraphBuilder().build(self._repository(Path(temporary)))
        engine = GraphQueryEngine(snapshot)
        search = engine.search("helper")
        self.assertEqual(search["matches"][0]["stable_id"], "python:pkg.core.helper:function")
        bootstrap = engine.bootstrap(max_nodes=5)
        self.assertEqual(len(bootstrap["nodes"]), 5)
        risks = engine.risks(limit=20)
        self.assertIn("READS_ENV", risks["by_kind"])
        self.assertIn("MUTABLE_GLOBAL", risks["by_kind"])
        self.assertIn("LOADS_RESOURCE", risks["by_kind"])
        self.assertNotIn("DECORATED_BY", risks["by_kind"])
        closure = engine.closure(["python:pkg.core.Service.run:method"])
        self.assertTrue(
            any(node["stable_id"] == "python:pkg.core.helper:function" for node in closure["nodes"])
        )

    def test_protocol_enforces_character_budget(self) -> None:
        result = {"matches": [{"name": f"symbol-{index}", "detail": "x" * 100} for index in range(50)]}
        payload = response_payload(
            command="search",
            snapshot_id="a" * 64,
            result=result,
            max_chars=800,
        )
        encoded = dumps_response(payload)
        self.assertLessEqual(len(encoded), 800)
        self.assertTrue(payload["truncated_by_budget"])
        self.assertGreater(payload["result"]["budget_omitted"]["matches"], 0)

    def test_tree_sitter_incremental_changed_ranges_api(self) -> None:
        backend = TreeSitterBackend()
        old_tree = backend.parse("python", b"value = 1\n")
        old_tree.edit(
            start_byte=8,
            old_end_byte=9,
            new_end_byte=14,
            start_point=(0, 8),
            old_end_point=(0, 9),
            new_end_point=(0, 14),
        )
        new_tree = backend.parse("python", b"value = call()\n", old_tree=old_tree)
        self.assertTrue(backend.changed_ranges(old_tree, new_tree))

    def test_parser_lock_matches_host_and_both_agent_images(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        lock_path = repository_root / "harness" / "config" / "repo_graph_requirements.lock"
        requirements = {
            name: version
            for line in lock_path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
            for name, version in [line.split("==", 1)]
        }
        self.assertEqual(requirements["tree-sitter"], importlib.metadata.version("tree-sitter"))
        self.assertEqual(
            requirements["tree-sitter-python"],
            importlib.metadata.version("tree-sitter-python"),
        )
        self.assertEqual(requirements["tree-sitter-go"], importlib.metadata.version("tree-sitter-go"))
        for dockerfile in ("Dockerfile.agent", "Dockerfile.agent-go"):
            content = (repository_root / "docker" / dockerfile).read_text(encoding="utf-8")
            self.assertIn("repo_graph_requirements.lock", content)

    def test_cli_build_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            output = root / "graph"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                build_code = graph_cli(
                    ["build", "--repo", str(repository), "--output", str(output)]
                )
            self.assertEqual(build_code, 0)
            build_result = json.loads(stdout.getvalue())
            self.assertEqual(build_result["counts"]["parse_error_files"], 0)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                search_code = graph_cli(
                    ["search", "--graph", str(output), "configured", "--max-chars", "2000"]
                )
            self.assertEqual(search_code, 0)
            search_result = json.loads(stdout.getvalue())
            self.assertEqual(search_result["result"]["matches"][0]["name"], "configured")

    def test_runtime_cache_overlay_default_cli_and_submission_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "run-one" / "workspace"
            agent_output = root / "run-one" / "agent"
            repository = self._repository(workspace, "repo")
            (workspace / "public_tests").mkdir()
            (workspace / "public_tests" / "test_public.py").write_text(
                "def test_helper(): pass\n", encoding="utf-8"
            )
            (workspace / "submission").mkdir()
            metadata = {
                "task_id": "sample__helper__001",
                "feature": {
                    "source_entrypoints": ["pkg.core.helper"],
                    "included_behaviors": ["increment one integer"],
                },
                "output": {
                    "package": "featurelifted",
                    "import": "from featurelifted import helper",
                    "callable": "featurelifted.helper",
                },
                "environment": {"forbidden_imports": ["pkg"]},
                "tests": {"public": "public_tests/"},
            }
            (workspace / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            task_file = workspace / "TASK.md"
            task_file.write_text("Implement helper.\n", encoding="utf-8")
            cache = root / "cache"
            env = {MODE_ENV: "closure", CACHE_DIR_ENV: str(cache)}

            state = initialize_repo_graph(
                workspace_dir=workspace,
                agent_output_dir=agent_output,
                config_env=env,
            )
            self.assertIsNotNone(state)
            assert state is not None
            append_repo_graph_prompt(task_file, state)
            self.assertIn("Repository Semantic Graph", task_file.read_text(encoding="utf-8"))
            bootstrap = (state.root / "bootstrap.md").read_text(encoding="utf-8")
            self.assertLessEqual(len(bootstrap), 4096)
            self.assertIn("flb-rsg search", bootstrap)
            self.assertIn("flb-rsg inspect", bootstrap)
            self.assertIn("flb-rsg support", bootstrap)
            self.assertNotIn("flb-rsg submission-check", bootstrap)
            self.assertIn("Bootstrap: `tool_only`", bootstrap)
            self.assertIn("prefer `flb-rsg support", bootstrap)
            build = json.loads((agent_output / "repo_graph_build.json").read_text(encoding="utf-8"))
            self.assertFalse(build["cache"]["hit"])
            self.assertEqual(build["input_scope"]["hidden_test_inputs"], 0)
            overlay = json.loads((state.root / "task_overlay.json").read_text(encoding="utf-8"))
            self.assertEqual(overlay["entrypoint_mapping"][0]["status"], "mapped")
            closure_digest = json.loads(
                (state.root / "closure_overlay.json").read_text(encoding="utf-8")
            )["closure_digest"]

            stdout = io.StringIO()
            with mock.patch.dict(
                "os.environ",
                {
                    ROOT_ENV: str(state.root),
                    "FEATURELIFTBENCH_AGENT_OUTPUT_DIR": str(agent_output),
                    "FEATURELIFTBENCH_SUBMISSION_DIR": str(workspace / "submission"),
                    "FEATURELIFTBENCH_WORKSPACE": str(workspace),
                },
                clear=False,
            ), contextlib.redirect_stdout(stdout):
                code = graph_cli(["search", "helper"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["result"]["matches"][0]["name"], "helper")
            self.assertEqual(len((agent_output / "repo_graph_queries.jsonl").read_text().splitlines()), 1)

            stdout = io.StringIO()
            with mock.patch.dict(
                "os.environ",
                {
                    ROOT_ENV: str(state.root),
                    "FEATURELIFTBENCH_SUBMISSION_DIR": str(workspace / "submission"),
                },
                clear=False,
            ), contextlib.redirect_stdout(stdout):
                support_code = graph_cli(
                    ["support", "--seed", "pkg.core.helper", "--budget-tokens", "2000"]
                )
            self.assertEqual(support_code, 0)
            support_result = json.loads(stdout.getvalue())["result"]
            self.assertEqual(support_result["status"], "ok")
            self.assertTrue(support_result["core"])
            self.assertIn("budget", support_result)
            self.assertLessEqual(
                support_result["budget"]["used_tokens"],
                support_result["budget"]["limit_tokens"],
            )

            package = workspace / "submission" / "featurelifted"
            package.mkdir()
            (package / "__init__.py").write_text(
                "def helper(value):\n    return value + 1\n", encoding="utf-8"
            )
            stdout = io.StringIO()
            with mock.patch.dict(
                "os.environ",
                {
                    ROOT_ENV: str(state.root),
                    "FEATURELIFTBENCH_SUBMISSION_DIR": str(workspace / "submission"),
                },
                clear=False,
            ), contextlib.redirect_stdout(stdout):
                check_code = graph_cli(["submission-check"])
            self.assertEqual(check_code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["result"]["sync"]["revision"], 1)
            first_sync = sync_submission(state.root, workspace / "submission")
            second_sync = sync_submission(state.root, workspace / "submission")
            self.assertFalse(first_sync["changed"])
            self.assertEqual(first_sync["revision"], 1)
            self.assertFalse(second_sync["changed"])
            self.assertEqual(second_sync["revision"], 1)
            comparison = compare_submission(
                state.root,
                workspace / "submission",
                source_repository=repository,
            )
            self.assertEqual(comparison["classification_counts"]["copied"], 1)
            self.assertEqual(comparison["gaps"]["missing_providers"], [])
            usage = finalize_repo_graph(state, submission_dir=workspace / "submission")
            self.assertTrue(usage["search_queried"])
            self.assertTrue(usage["support_queried"])
            self.assertTrue(usage["optional_tool_used"])
            self.assertTrue(usage["adoption_compliant"])
            self.assertEqual(usage["mechanism_status"], "optional_tools_used")
            self.assertTrue(usage["fresh_submission_check"])
            audit_rows = [
                json.loads(line)
                for line in (agent_output / "repo_graph_queries.jsonl").read_text().splitlines()
            ]
            self.assertTrue(all(row["result"] == {} for row in audit_rows))
            self.assertTrue(all(len(row["result_digest"]) == 64 for row in audit_rows))

            workspace_two = root / "run-two" / "workspace"
            agent_two = root / "run-two" / "agent"
            shutil.copytree(workspace, workspace_two)
            shutil.rmtree(workspace_two / "submission")
            (workspace_two / "submission").mkdir()
            state_two = initialize_repo_graph(
                workspace_dir=workspace_two,
                agent_output_dir=agent_two,
                config_env=env,
            )
            assert state_two is not None
            build_two = json.loads((agent_two / "repo_graph_build.json").read_text(encoding="utf-8"))
            self.assertTrue(build_two["cache"]["hit"])
            self.assertEqual(
                json.loads((state_two.root / "closure_overlay.json").read_text(encoding="utf-8"))[
                    "closure_digest"
                ],
                closure_digest,
            )

    def test_failed_query_is_audited_without_exposing_response_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            agent_output = root / "agent"
            self._repository(workspace, "repo")
            (workspace / "public_tests").mkdir()
            (workspace / "submission").mkdir()
            (workspace / "metadata.json").write_text(
                json.dumps(
                    {
                        "task_id": "sample__audit__001",
                        "feature": {"source_entrypoints": ["pkg.core.helper"]},
                        "output": {"package": "featurelifted"},
                    }
                ),
                encoding="utf-8",
            )
            state = initialize_repo_graph(
                workspace_dir=workspace,
                agent_output_dir=agent_output,
                config_env={MODE_ENV: "closure", BOOTSTRAP_MAX_CHARS_ENV: "4096"},
            )
            assert state is not None
            with mock.patch.dict("os.environ", {ROOT_ENV: str(state.root)}, clear=False), contextlib.redirect_stderr(io.StringIO()):
                code = graph_cli(["inspect", "definitely-missing-node"])
            self.assertEqual(code, 2)
            row = json.loads((agent_output / "repo_graph_queries.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["status"], "failed")
            self.assertEqual(row["error_type"], "ValueError")
            self.assertEqual(row["response_chars"], 0)

    def test_claim_evidence_state_machine_and_revision_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            agent_output = root / "agent"
            self._repository(workspace, "repo")
            (workspace / "public_tests").mkdir()
            (workspace / "submission").mkdir()
            metadata = {
                "task_id": "sample__evidence__001",
                "feature": {
                    "source_entrypoints": ["pkg.core.helper"],
                    "included_behaviors": ["increment one integer"],
                },
                "output": {"package": "featurelifted"},
                "environment": {
                    "python": "3.11",
                    "network": False,
                    "forbidden_imports": ["pkg"],
                },
            }
            (workspace / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            state = initialize_repo_graph(
                workspace_dir=workspace,
                agent_output_dir=agent_output,
                config_env={MODE_ENV: "evidence"},
            )
            assert state is not None
            detectors = json.loads((state.root / "risk_detectors.json").read_text())
            self.assertGreater(detectors["count"], 0)
            self.assertTrue(
                all(item["source_cue"] and item["probe_rationale"] for item in detectors["detections"])
            )
            self.assertEqual(detectors["unmatched_low_precision_cues_exposed"], 0)
            stdout = io.StringIO()
            with mock.patch.dict("os.environ", {ROOT_ENV: str(state.root)}, clear=False), contextlib.redirect_stdout(stdout):
                detector_code = graph_cli(["detectors"])
            self.assertEqual(detector_code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["result"]["count"], detectors["count"])

            ledger = RepoGraphLedger(state.root)
            stdout = io.StringIO()
            with mock.patch.dict("os.environ", {ROOT_ENV: str(state.root)}, clear=False), contextlib.redirect_stdout(stdout):
                claim_code = graph_cli(
                    [
                        "claim",
                        "add",
                        "--subject",
                        "python:pkg.core.helper:function",
                        "--predicate",
                        "IMPLEMENTS_BEHAVIOR",
                        "--object",
                        "behavior:B001",
                        "--classification",
                        "required",
                        "--confidence",
                        "0.8",
                    ]
                )
            self.assertEqual(claim_code, 0)
            claim = json.loads(stdout.getvalue())["result"]
            with self.assertRaisesRegex(ValueError, "observed requires"):
                ledger.update_claim(claim["claim_id"], status="observed")
            runtime_evidence = ledger.record_evidence(
                kind="runtime_probe",
                probe_type="representative_call",
                evidence_class="runtime",
                status="supports",
                result_summary="helper returned the expected increment",
                claim_ids=[claim["claim_id"]],
            )
            observed = ledger.update_claim(
                claim["claim_id"],
                status="observed",
                evidence_ids=[runtime_evidence["evidence_id"]],
            )
            self.assertEqual(observed["status"], "observed")
            with self.assertRaisesRegex(ValueError, "two independent"):
                ledger.update_claim(claim["claim_id"], status="verified")
            static_evidence = ledger.record_evidence(
                kind="static_inspection",
                probe_type="definition_and_dependency_check",
                evidence_class="static",
                status="supports",
                result_summary="definition and direct dependency were inspected",
                claim_ids=[claim["claim_id"]],
            )
            verified = ledger.update_claim(
                claim["claim_id"],
                status="verified",
                evidence_ids=[static_evidence["evidence_id"]],
            )
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(
                RepoGraphLedger(state.root).claim_states()[claim["claim_id"]]["status"],
                "verified",
            )
            ledger.record_evidence(
                kind="verification_result",
                probe_type="final_verification",
                evidence_class="api_probe",
                status="supports",
                result_summary="fresh final API verification passed",
            )
            self.assertTrue(ledger.stopping_guard()["ready"])
            with self.assertRaisesRegex(ValueError, "sensitive"):
                ledger.record_evidence(
                    kind="runtime_probe",
                    probe_type="bad_probe",
                    evidence_class="runtime",
                    status="failed",
                    result_summary="api_key=sk-secret",
                )

            package = workspace / "submission" / "featurelifted"
            package.mkdir()
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            synced = sync_submission(state.root, workspace / "submission")
            self.assertEqual(synced["revision"], 1)
            freshness = ledger.freshness_report()
            self.assertIn(claim["claim_id"], freshness["stale_claims"])
            guard = ledger.stopping_guard()
            self.assertFalse(guard["ready"])
            self.assertIn("stale_claims", guard["blockers"])
            self.assertIn("missing_fresh_final_verification", guard["blockers"])

    def test_operational_support_respects_budget_and_seed_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = self._repository(Path(temporary))
            snapshot = GraphBuilder().build(repository)
            engine = GraphQueryEngine(snapshot)
            from featureliftbench.repo_graph.support import build_operational_support

            result = build_operational_support(
                engine,
                ["helper"],
                budget_tokens=1_500,
                max_nodes=40,
            )
            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["seeds"])
            self.assertTrue(result["core"])
            self.assertLessEqual(
                result["budget"]["used_tokens"],
                result["budget"]["limit_tokens"],
            )
            ambiguous = build_operational_support(
                engine,
                ["definitely_missing_symbol_xyz"],
                budget_tokens=1_500,
            )
            self.assertEqual(ambiguous["status"], "ambiguous_seeds")
            self.assertTrue(ambiguous["ambiguous_seeds"])

            # Prefer class/function symbols over dependency/module name ties.
            class_hits = [
                node
                for node in snapshot.nodes
                if node.kind == "class" and node.name == "Service"
            ]
            if class_hits:
                preferred = build_operational_support(
                    engine,
                    ["Service"],
                    budget_tokens=1_500,
                )
                self.assertEqual(preferred["status"], "ok")
            self.assertTrue(
                any(seed.endswith(":class") for seed in preferred["seeds"])
            )
            self.assertIn("guidance", preferred)
            self.assertTrue(preferred["guidance"].get("start_here_files"))
            from featureliftbench.repo_graph.support import render_compact_guidance

            md = render_compact_guidance(preferred)
            self.assertIn("RSG start-here", md)
            self.assertIn("Files", md)


if __name__ == "__main__":
    unittest.main()
