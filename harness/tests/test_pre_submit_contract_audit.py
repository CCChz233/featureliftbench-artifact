"""Pre-submit explicit-contract audit parser, prompts, and exclusivity."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.agent_runner import prepare_agent_workspace
from featureliftbench.metadata import load_metadata
from featureliftbench.openhands_runner import OpenHandsRunnerConfig
from featureliftbench.openhands_runner import _build_openhands_prompt
from featureliftbench.pre_submit_contract_audit import parse_pre_submit_audit
from featureliftbench.pre_submit_contract_audit import task_appendix
from featureliftbench.pre_submit_contract_audit import write_pre_submit_audit


class PreSubmitAuditParserTests(unittest.TestCase):
    def test_detects_gap_and_continued_edit(self) -> None:
        events = [
            {
                "kind": "MessageAction",
                "thought": (
                    "PRE-SUBMIT CONTRACT AUDIT\n"
                    "- B001: gap missing export\n"
                    "AUDIT_RESULT: gaps\n"
                ),
            },
            {
                "kind": "FileEditorAction",
                "tool_name": "file_editor",
                "action": {"path": "submission/featurelifted/mod.py"},
            },
        ]
        payload = parse_pre_submit_audit(events)
        self.assertTrue(payload["audit_executed"])
        self.assertTrue(payload["explicit_gap_found"])
        self.assertTrue(payload["continued_after_gap"])
        self.assertEqual(payload["audit_result"], "gaps")

    def test_complete_audit_does_not_mark_gap(self) -> None:
        events = [
            {
                "kind": "MessageAction",
                "thought": (
                    "PRE-SUBMIT CONTRACT AUDIT\n"
                    "- B001: covered\n"
                    "AUDIT_RESULT: complete\n"
                ),
            }
        ]
        payload = parse_pre_submit_audit(events)
        self.assertTrue(payload["audit_executed"])
        self.assertFalse(payload["explicit_gap_found"])
        self.assertFalse(payload["continued_after_gap"])
        self.assertEqual(payload["audit_result"], "complete")

    def test_missing_trajectory_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "openhands_events.jsonl"
            payload = parse_pre_submit_audit(missing)
        self.assertEqual(payload["audit_executed"], "unknown")
        self.assertEqual(payload["explicit_gap_found"], "unknown")

    def test_write_pre_submit_audit_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "events.jsonl"
            events_path.write_text(
                '{"thought": "PRE-SUBMIT CONTRACT AUDIT\\nAUDIT_RESULT: complete"}\n',
                encoding="utf-8",
            )
            output = Path(tmp) / "pre_submit_audit.json"
            payload = write_pre_submit_audit(events_path, output, public_pass=False)
            self.assertTrue(output.is_file())
            self.assertTrue(payload["audit_executed"])
            self.assertFalse(payload["public_pass"])


class PreSubmitPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "sanity"
            / "iniconfig__parse_config__001"
        )
        self.metadata = load_metadata(self.task_dir).data

    def test_appendix_forbids_inventing_contracts(self) -> None:
        text = task_appendix()
        self.assertIn("PRE-SUBMIT CONTRACT AUDIT", text)
        self.assertIn("AUDIT_RESULT:", text)
        self.assertIn("Do not invent a new contract", text)
        self.assertIn("flb-contract-check", text)

    def test_workspace_task_contains_audit_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(pre_submit_contract_audit=True),
            )
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertIn("PRE-SUBMIT CONTRACT AUDIT", prompt)
            self.assertIn("Do not invent a new contract", prompt)
            self.assertFalse((workspace / "flb-contract-check").exists())
            self.assertFalse((workspace / "public_tests").exists())

    def test_openhands_prompt_contains_audit_instructions(self) -> None:
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
                {"FEATURELIFTBENCH_PRE_SUBMIT_CONTRACT_AUDIT": "1"},
                clear=False,
            ):
                text = _build_openhands_prompt(config)
            self.assertIn("PRE-SUBMIT CONTRACT AUDIT", text)
            self.assertIn("Do not invent new contracts", text)
            self.assertIn("AUDIT_RESULT:", text)


class PreSubmitExclusivityTests(unittest.TestCase):
    def test_arm_name_and_exclusivity(self) -> None:
        self.assertEqual(
            AblationOptions(pre_submit_contract_audit=True).ablation_arm,
            "pre_submit_contract_audit",
        )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                pre_submit_contract_audit=True,
                test_first_lift=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                pre_submit_contract_audit=True,
                adaptive_budget_v2=True,
            )


if __name__ == "__main__":
    unittest.main()
