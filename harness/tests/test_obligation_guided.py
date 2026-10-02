"""Tests for Obligation-Guided Feature Lifting ledger, workspace, audit, and sample."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.agent_config import load_agent_run_config
from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_runner import prepare_agent_workspace
from featureliftbench.obligation_guided import build_obligation_ledger
from featureliftbench.obligation_guided import collect_ledger_metrics
from featureliftbench.obligation_guided import install_obligation_guided_workspace
from featureliftbench.obligation_guided import task_appendix
from featureliftbench.obligation_guided.sample import sample_pilot30
from featureliftbench.openhands_runner import OpenHandsRunnerConfig
from featureliftbench.openhands_runner import _build_openhands_prompt


def _public_spec() -> dict:
    return {
        "title": "Demo",
        "summary": "Demo summary",
        "required_api": [
            {
                "path": "featurelifted.Foo",
                "kind": "class",
                "members": [
                    {"path": "featurelifted.Foo.bar", "kind": "method"},
                ],
            },
            {"path": "featurelifted.FooError", "kind": "exception"},
        ],
        "behaviors": [
            {"id": "B001", "text": "Foo validates empty input."},
            {"id": "B002", "text": "Invalid names raise FooError."},
        ],
        "source_entrypoints": ["should.not.leak"],
        "isolation_behavior": {
            "id": "B003",
            "text": "does not import upstream_pkg",
        },
    }


class ObligationLedgerTests(unittest.TestCase):
    def test_ledger_has_api_and_behaviors_without_entrypoints(self) -> None:
        ledger = build_obligation_ledger(_public_spec())
        ids = [row["id"] for row in ledger["obligations"]]
        self.assertIn("API:featurelifted.Foo", ids)
        self.assertIn("API:featurelifted.Foo.bar", ids)
        self.assertIn("API:featurelifted.FooError", ids)
        self.assertIn("B001", ids)
        self.assertIn("B002", ids)
        self.assertIn("B003", ids)
        self.assertEqual(ledger["frozen_ids"], ids)
        dumped = json.dumps(ledger)
        self.assertNotIn("source_entrypoints", dumped)
        self.assertNotIn("should.not.leak", dumped)
        for row in ledger["obligations"]:
            self.assertEqual(row["repo_evidence"]["path"], "")
            self.assertEqual(row["implementation"]["path"], "")
            self.assertEqual(row["verification"]["status"], "?")


class ObligationWorkspaceTests(unittest.TestCase):
    def test_install_writes_ledger_not_checker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_obligation_guided_workspace(root, public_spec=_public_spec())
            ledger_path = root / "obligation_ledger.json"
            self.assertTrue(ledger_path.is_file())
            self.assertFalse((root / "run_contract_check.py").exists())
            self.assertFalse((root / "contract_cases").exists())
            self.assertFalse((root / "flb-contract-check").exists())
            self.assertFalse((root / "run_cgvl_check.py").exists())
            payload = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertNotIn("source_entrypoints", json.dumps(payload))

    def test_audit_reports_gaps_then_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_obligation_guided_workspace(root, public_spec=_public_spec())
            empty = collect_ledger_metrics(root)
            self.assertTrue(empty["ledger_present"])
            self.assertFalse(empty["coverage_complete"])
            self.assertTrue(empty["finished_with_gaps"])
            self.assertEqual(empty["rows_both_cited"], 0)
            ledger = json.loads((root / "obligation_ledger.json").read_text())
            for row in ledger["obligations"]:
                row["repo_evidence"]["path"] = "repo/foo.py"
                row["implementation"]["path"] = "submission/featurelifted/foo.py"
                row["verification"]["status"] = "cited"
                row["verification"]["citation"] = "repo/foo.py:10"
            (root / "obligation_ledger.json").write_text(
                json.dumps(ledger), encoding="utf-8"
            )
            filled = collect_ledger_metrics(root)
            self.assertTrue(filled["coverage_complete"])
            self.assertFalse(filled["finished_with_gaps"])
            self.assertEqual(filled["invented_row_ids"], [])

    def test_invented_rows_break_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_obligation_guided_workspace(root, public_spec=_public_spec())
            ledger = json.loads((root / "obligation_ledger.json").read_text())
            extra = dict(ledger["obligations"][0])
            extra["id"] = "HIDDEN_CASE"
            ledger["obligations"].append(extra)
            for row in ledger["obligations"]:
                row["repo_evidence"]["path"] = "repo/foo.py"
                row["implementation"]["path"] = "submission/featurelifted/foo.py"
            (root / "obligation_ledger.json").write_text(
                json.dumps(ledger), encoding="utf-8"
            )
            metrics = collect_ledger_metrics(root)
            self.assertIn("HIDDEN_CASE", metrics["invented_row_ids"])
            self.assertFalse(metrics["coverage_complete"])

    def test_appendix_forbids_tests_and_hidden(self) -> None:
        text = task_appendix()
        self.assertIn("obligation_ledger.json", text)
        self.assertIn("Do not add, delete, split, or rename rows", text)
        self.assertIn("self-written pytest is not", text)
        self.assertIn("hidden_tests", text)


class ObligationAblationTests(unittest.TestCase):
    def test_arm_name_and_exclusivity(self) -> None:
        self.assertEqual(
            AblationOptions(obligation_guided=True).ablation_arm,
            "obligation_guided",
        )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(obligation_guided=True, spec_adversarial_self_test=True)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(obligation_guided=True, pre_submit_contract_audit=True)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(obligation_guided=True, cgvl=True)

    def test_example_profile_keeps_main_envelope(self) -> None:
        config_file = (
            Path(__file__).resolve().parents[1] / "config" / "agents.example.toml"
        )
        loaded = load_agent_run_config(
            base_config=AgentRunConfig(agent="openhands"),
            config_path=config_file,
            profile_name="openhands_deepseek_v4_flash_obligation_guided",
        )
        self.assertEqual(loaded.summary["ablation_arm"], "obligation_guided")
        self.assertEqual(loaded.summary["openhands_condenser_mode"], "token")
        self.assertEqual(loaded.summary["context_window_tokens"], 131072)
        self.assertEqual(loaded.summary["openhands_max_steps"], 120)
        self.assertTrue(loaded.summary["obligation_guided"])

    def test_openhands_prompt_mentions_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "TASK.md"
            task.write_text("Implement the feature.\n", encoding="utf-8")
            config = OpenHandsRunnerConfig(
                workspace_dir=root,
                task_file=task,
                submission_dir=root / "submission",
                agent_output_dir=root / "agent",
                model="test-model",
            )
            with mock.patch.dict(
                "os.environ",
                {"FEATURELIFTBENCH_OBLIGATION_GUIDED": "1"},
                clear=False,
            ):
                text = _build_openhands_prompt(config)
            self.assertIn("obligation_ledger.json", text)
            self.assertNotIn("run_contract_check.py", text)


class ObligationSampleTests(unittest.TestCase):
    def test_stratified_sample_prefers_cac_then_drift(self) -> None:
        rows = []
        for i in range(20):
            rows.append(
                {
                    "task_id": f"public_drift_{i:02d}",
                    "model": "flash",
                    "first_failure_stage": "public",
                    "root_cause_primary": "behavior_drift",
                }
            )
        for i in range(20):
            rows.append(
                {
                    "task_id": f"hidden_drift_{i:02d}",
                    "model": "flash",
                    "first_failure_stage": "hidden",
                    "root_cause_primary": "behavior_drift",
                }
            )
        rows.append(
            {
                "task_id": "public_cac_00",
                "model": "flash",
                "first_failure_stage": "public",
                "root_cause_primary": "contract_api_completion",
            }
        )
        rows.append(
            {
                "task_id": "hidden_cac_00",
                "model": "flash",
                "first_failure_stage": "hidden",
                "root_cause_primary": "contract_api_completion",
            }
        )
        payload = sample_pilot30(rows, n_public=15, n_hidden=15, model="flash")
        self.assertEqual(len(payload["task_ids"]), 30)
        self.assertIn("public_cac_00", payload["task_ids"])
        self.assertIn("hidden_cac_00", payload["task_ids"])
        self.assertGreaterEqual(payload["cause_counts"].get("contract_api_completion", 0), 2)

    def test_sample_fails_if_pool_too_small(self) -> None:
        rows = [
            {
                "task_id": "only_public",
                "model": "flash",
                "first_failure_stage": "public",
                "root_cause_primary": "behavior_drift",
            }
        ]
        with self.assertRaises(ValueError):
            sample_pilot30(rows, n_public=15, n_hidden=15, model="flash")

    def test_excludes_empty_submissions_and_defects(self) -> None:
        rows = [
            {
                "task_id": "empty",
                "model": "flash",
                "first_failure_stage": "public",
                "root_cause_primary": "agent_process_non_delivery",
            },
            {
                "task_id": "defect",
                "model": "flash",
                "first_failure_stage": "public",
                "root_cause_primary": "task_or_evaluator_defect",
                "validity_override": "benchmark_invalid_candidate",
            },
        ]
        with self.assertRaises(ValueError):
            sample_pilot30(rows, n_public=1, n_hidden=1, model="flash")


class ObligationPrepareWorkspaceTests(unittest.TestCase):
    def test_prepare_installs_ledger_on_task_with_public_spec(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "sanity"
            / "iniconfig__parse_config__001"
        )
        if not (task_dir / "metadata.json").is_file():
            self.skipTest("sanity task metadata unavailable")
        from featureliftbench.metadata import load_metadata

        metadata = load_metadata(task_dir).data
        public_spec = metadata.get("public_spec")
        if not isinstance(public_spec, dict) or not public_spec:
            self.skipTest("sanity task has no public_spec")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                task_dir,
                workspace,
                metadata,
                ablation=AblationOptions(obligation_guided=True),
            )
            self.assertTrue((workspace / "obligation_ledger.json").is_file())
            self.assertFalse((workspace / "run_contract_check.py").exists())
            self.assertFalse((workspace / "public_tests").exists())
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertIn("Obligation-Guided Feature Lifting", prompt)


if __name__ == "__main__":
    unittest.main()
