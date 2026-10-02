from __future__ import annotations

import json
import unittest
from pathlib import Path

from featureliftbench.agent_adapters import SUPPORTED_AGENTS
from featureliftbench.catalog import CatalogError
from featureliftbench.catalog import check_catalog
from featureliftbench.catalog import emit_bash
from featureliftbench.catalog import get_agent
from featureliftbench.catalog import get_method
from featureliftbench.catalog import get_suite
from featureliftbench.catalog import load_catalog
from featureliftbench.catalog import resolve_run
from featureliftbench.catalog import resolved_payload
from featureliftbench.cli import main


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()

    def test_check_passes_on_repo_registries(self) -> None:
        self.assertEqual(check_catalog(self.catalog), [])

    def test_agent_aliases_normalize_to_openhands_cli(self) -> None:
        for name in ("openhands", "openhands-agent", "openhandsagent"):
            spec = get_agent(self.catalog, name)
            self.assertEqual(spec.id, "openhands")
            self.assertEqual(spec.cli_name, "openhands-agent")
            self.assertIn(spec.cli_name, SUPPORTED_AGENTS)

    def test_method_aliases_match_legacy_arms(self) -> None:
        cases = {
            "main": "main",
            "nopublic": "main",
            "hints": "entrypoint_hint",
            "public": "public_feedback",
            "short": "short_prompt",
            "pruned": "pruned_context",
            "contract_only": "contract_only",
            "no-source": "contract_only",
            "td": "td_cognition",
            "exec": "exec_contract",
            "cgcc": "cgcc_lite",
            "fcec": "fcec",
            "sac": "self_contract",
            "tfl": "test_first_lift",
            "p0": "p0",
        }
        for alias, method_id in cases.items():
            self.assertEqual(get_method(self.catalog, alias).id, method_id)

    def test_python200_hard_main_openhands_resolve(self) -> None:
        resolved = resolve_run(
            agent="openhands",
            method="main",
            benchmark="python200_hard",
            catalog=self.catalog,
        )
        self.assertEqual(resolved.agent_cli, "openhands-agent")
        self.assertEqual(resolved.profile, "openhands_deepseek_v4_flash_main")
        self.assertEqual(resolved.tasks_root, "benchmark/python200_hard_tasks")
        self.assertEqual(
            resolved.source_registry,
            "benchmark/sources/python200_hard_registry.json",
        )
        self.assertIn("--no-agent-source-hints", resolved.run_agent_flags)
        self.assertIn("--no-agent-public-tests", resolved.run_agent_flags)
        payload = resolved_payload(resolved)
        self.assertTrue(payload["paper_table"])
        self.assertIn("CATALOG_PROFILE=", emit_bash(payload))

    def test_python200_hard_standard_is_task_file_subset(self) -> None:
        suite = get_suite(self.catalog, "python200_hard_standard")
        self.assertEqual(suite.tasks_root, "benchmark/python200_hard_tasks")
        self.assertEqual(
            suite.task_file,
            "harness/config/experiments/python200_hard_standard.txt",
        )
        self.assertFalse(suite.paper_main)
        self.assertEqual(suite.status, "unreleased")
        resolved = resolve_run(
            agent="openhands",
            method="main",
            benchmark="163-standard",
            catalog=self.catalog,
        )
        payload = resolved_payload(resolved)
        self.assertEqual(payload["benchmark_id"], "python200_hard_standard")
        self.assertEqual(payload["task_file"], suite.task_file)
        self.assertIn("CATALOG_TASK_FILE=", emit_bash(payload))

    def test_runtime_agents_share_main_method(self) -> None:
        dsh = resolve_run(
            agent="dsh",
            method="main",
            catalog=self.catalog,
        )
        codex = resolve_run(
            agent="codex",
            method="main",
            catalog=self.catalog,
        )
        self.assertEqual(dsh.agent_cli, "deepseek-harness")
        self.assertEqual(dsh.profile, "dsh_deepseek_v4_flash_main")
        self.assertFalse(dsh.agent.paper_table)
        self.assertEqual(codex.agent_cli, "codex")
        self.assertEqual(codex.profile, "codex_deepseek_v4_flash_main")

    def test_contract_only_is_not_paper_table(self) -> None:
        spec = get_method(self.catalog, "no-source")
        self.assertEqual(spec.id, "contract_only")
        self.assertFalse(spec.paper_table)
        self.assertEqual(spec.status, "ablation")
        self.assertIn("--source-context", spec.run_agent_flags)
        self.assertIn("contract_only", spec.run_agent_flags)
        main = get_method(self.catalog, "main")
        self.assertTrue(main.paper_table)
        self.assertIn("full_repository", main.run_agent_flags)
        self.assertNotIn("contract_only", main.run_agent_flags)

    def test_public_feedback_mounts_public_tests(self) -> None:
        flags = get_method(self.catalog, "public_feedback").run_agent_flags
        self.assertIn("--agent-public-tests", flags)
        self.assertNotIn("--agent-source-hints", flags)

    def test_autosaddler_is_screening_not_paper_table(self) -> None:
        method = get_method(self.catalog, "self-harness")
        self.assertEqual(method.id, "autosaddler")
        self.assertFalse(method.paper_table)
        self.assertEqual(method.status, "screening")
        self.assertEqual(
            method.profiles["openhands"],
            "openhands_deepseek_v4_flash_main",
        )

    def test_cgvl_is_screening_not_paper_table(self) -> None:
        method = get_method(self.catalog, "contract-guided-verification")
        self.assertEqual(method.id, "cgvl")
        self.assertFalse(method.paper_table)
        self.assertEqual(method.status, "screening")
        self.assertIn("--cgvl", method.run_agent_flags)
        self.assertEqual(
            method.profiles["openhands"],
            "openhands_deepseek_v4_flash_cgvl",
        )

    def test_obligation_guided_is_screening_not_paper_table(self) -> None:
        method = get_method(self.catalog, "ogfl")
        self.assertEqual(method.id, "obligation_guided")
        self.assertFalse(method.paper_table)
        self.assertEqual(method.status, "screening")
        self.assertIn("--obligation-guided", method.run_agent_flags)
        self.assertEqual(
            method.profiles["openhands"],
            "openhands_deepseek_v4_flash_obligation_guided",
        )

    def test_unknown_method_errors(self) -> None:
        with self.assertRaises(CatalogError):
            get_method(self.catalog, "not-a-method")

    def test_v1_has_no_profile_for_codex(self) -> None:
        with self.assertRaises(CatalogError):
            resolve_run(agent="codex", method="v1", catalog=self.catalog)

    def test_cli_catalog_check_and_list(self) -> None:
        self.assertEqual(main(["catalog", "check"]), 0)
        self.assertEqual(main(["catalog", "list", "--kind", "agents"]), 0)

    def test_cli_catalog_resolve_json(self) -> None:
        import io
        from unittest.mock import patch

        buffer = io.StringIO()
        with patch("sys.stdout", buffer):
            code = main(
                [
                    "catalog",
                    "resolve",
                    "--agent",
                    "openhands",
                    "--method",
                    "main",
                    "--benchmark",
                    "python200_hard",
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["agent_cli"], "openhands-agent")
        self.assertEqual(payload["benchmark_id"], "python200_hard")

    def test_paper_main_suite_root_exists(self) -> None:
        root = Path(__file__).resolve().parents[2]
        suite = self.catalog.suites["python200_hard"]
        self.assertTrue((root / suite.tasks_root).is_dir())
        self.assertTrue((root / suite.source_registry).is_file())


if __name__ == "__main__":
    unittest.main()
