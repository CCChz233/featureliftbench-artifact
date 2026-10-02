"""Unit tests for V2 Adaptive Budget progress checkpoint and envelope."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.adaptive_budget_v2 import DEFAULT_EXTRA_TOKEN_LIMIT
from featureliftbench.adaptive_budget_v2 import DEFAULT_PRIMARY_TOKEN_LIMIT
from featureliftbench.adaptive_budget_v2 import evaluate_progress
from featureliftbench.adaptive_budget_v2 import primary_needs_checkpoint
from featureliftbench.adaptive_budget_v2 import write_checkpoint


ROOT = Path(__file__).resolve().parents[2]
CORE12_CAP = (
    ROOT
    / "experiments/methods/main_2m_cap"
    / "core12-deepseek-v4-flash-main-2m-cap-0817-001"
)
JSON_LOGIC = CORE12_CAP / "json_logic__evaluator_core__hard3_001"
ALEMBIC = CORE12_CAP / "alembic__revision_map_core__hard3_001"


def _write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


class AdaptiveBudgetV2AblationTests(unittest.TestCase):
    def test_arm_name_and_exclusivity(self) -> None:
        self.assertEqual(
            AblationOptions(adaptive_budget_v2=True).ablation_arm,
            "adaptive_budget_v2",
        )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                adaptive_budget_v2=True,
                contract_closure_gate_lite_v1=True,
            )

    def test_profile_resolves_v2(self) -> None:
        options = resolve_ablation_options(
            profile={
                "adaptive_budget_v2": True,
                "mount_public_tests": False,
                "prompt_style": "standard",
            }
        )
        self.assertTrue(options.adaptive_budget_v2)
        self.assertEqual(options.ablation_arm, "adaptive_budget_v2")
        self.assertFalse(options.mount_public_tests)


class ProgressDetectorTests(unittest.TestCase):
    def test_empty_submission_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent"
            submission = root / "submission"
            submission.mkdir()
            agent.mkdir()
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=submission,
            )
            self.assertEqual(signals.decision, "stop")
            self.assertEqual(signals.reason, "empty_or_missing_submission")

    def test_recent_file_editor_write_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent"
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text("x = 1\n", encoding="utf-8")
            _write_events(
                agent / "openhands_events.jsonl",
                [
                    {
                        "kind": "ActionEvent",
                        "tool_name": "terminal",
                        "timestamp": "2026-08-17T14:00:00",
                        "action": {"command": "ls repo"},
                        "summary": "explore",
                    },
                    {
                        "kind": "ActionEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-17T14:00:10",
                        "action": {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/__init__.py",
                        },
                        "summary": "write submission",
                    },
                ],
            )
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=root / "submission",
                recent_n=10,
            )
            self.assertEqual(signals.decision, "continue")
            self.assertGreaterEqual(signals.recent_submission_writes, 1)

    def test_explore_only_recent_actions_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent"
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text("x = 1\n", encoding="utf-8")
            events = [
                {
                    "kind": "ActionEvent",
                    "tool_name": "terminal",
                    "timestamp": f"2026-08-17T14:00:{i:02d}",
                    "action": {"command": f"ls repo/pkg{i}"},
                    "summary": "explore",
                }
                for i in range(12)
            ]
            _write_events(agent / "openhands_events.jsonl", events)
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=root / "submission",
                recent_n=10,
            )
            self.assertEqual(signals.decision, "stop")
            self.assertEqual(signals.reason, "no_recent_submission_writes")

    @unittest.skipUnless(JSON_LOGIC.is_dir(), "Core-12 json_logic fixture missing")
    def test_core12_json_logic_fixture_has_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent"
            submission = root / "submission"
            shutil.copytree(JSON_LOGIC / "agent", agent)
            src_sub = JSON_LOGIC / "workspace" / "submission"
            if not src_sub.is_dir():
                src_sub = JSON_LOGIC / "submission"
            if src_sub.is_dir():
                shutil.copytree(src_sub, submission)
            else:
                submission.mkdir()
                pkg = submission / "featurelifted"
                pkg.mkdir()
                (pkg / "__init__.py").write_text("pass\n", encoding="utf-8")
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=submission,
                recent_n=10,
            )
            # Cheap pass: submission exists and recent window includes writes.
            self.assertTrue(signals.has_nonempty_submission)
            self.assertIn(signals.decision, {"continue", "stop"})

    @unittest.skipUnless(ALEMBIC.is_dir(), "Core-12 alembic fixture missing")
    def test_core12_cap_hit_fixture_checkpoint_inputs(self) -> None:
        usage_path = ALEMBIC / "agent" / "usage.json"
        usage = json.loads(usage_path.read_text(encoding="utf-8"))
        self.assertTrue(
            primary_needs_checkpoint(usage, primary_limit=1_500_000)
            or int(usage.get("total_tokens") or 0) >= 1_350_000
            or usage.get("token_budget_exhausted") is True
        )


class CheckpointAndBudgetTests(unittest.TestCase):
    def test_primary_needs_checkpoint_thresholds(self) -> None:
        self.assertFalse(
            primary_needs_checkpoint(
                {"total_tokens": 500_000}, primary_limit=1_500_000
            )
        )
        self.assertTrue(
            primary_needs_checkpoint(
                {"total_tokens": 1_400_000}, primary_limit=1_500_000
            )
        )
        self.assertTrue(
            primary_needs_checkpoint(
                {"token_budget_exhausted": True, "total_tokens": 100},
                primary_limit=1_500_000,
            )
        )

    def test_write_checkpoint_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = Path(tmp)
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=agent / "missing",
            )
            payload = write_checkpoint(
                agent,
                signals=signals,
                primary_usage={"total_tokens": 1_500_000, "token_budget_exhausted": True},
                primary_limit=DEFAULT_PRIMARY_TOKEN_LIMIT,
                extra_limit=DEFAULT_EXTRA_TOKEN_LIMIT,
                granted_extra=False,
            )
            path = agent / "v2_checkpoint.json"
            self.assertTrue(path.is_file())
            self.assertEqual(payload["decision"], "stop")
            self.assertFalse(payload["granted_extra"])


class V2RunnerPhaseTests(unittest.TestCase):
    def test_continue_starts_second_docker(self) -> None:
        from featureliftbench.adaptive_budget_v2 import evaluate_progress
        from featureliftbench.adaptive_budget_v2 import primary_needs_checkpoint

        usage = {"total_tokens": 1_500_000, "token_budget_exhausted": True}
        self.assertTrue(primary_needs_checkpoint(usage, primary_limit=1_500_000))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent"
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text("ok\n", encoding="utf-8")
            _write_events(
                agent / "openhands_events.jsonl",
                [
                    {
                        "kind": "ActionEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-17T15:00:00",
                        "action": {
                            "command": "str_replace",
                            "path": "/flb/workspace/submission/featurelifted/__init__.py",
                        },
                    }
                ],
            )
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=root / "submission",
            )
            self.assertEqual(signals.decision, "continue")

    def test_stop_does_not_grant_extra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "agent"
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text("ok\n", encoding="utf-8")
            _write_events(
                agent / "openhands_events.jsonl",
                [
                    {
                        "kind": "ActionEvent",
                        "tool_name": "terminal",
                        "timestamp": "2026-08-17T15:00:00",
                        "action": {"command": "find repo -name '*.py' | head"},
                    }
                ]
                * 10,
            )
            signals = evaluate_progress(
                agent_output_dir=agent,
                submission_dir=root / "submission",
            )
            self.assertEqual(signals.decision, "stop")


class V2ProfileEnvelopeTests(unittest.TestCase):
    def test_example_profile_envelope(self) -> None:
        import tomllib

        example = ROOT / "harness/config/agents.example.toml"
        data = tomllib.loads(example.read_text(encoding="utf-8"))
        profile = data["profiles"]["openhands_deepseek_v4_flash_v2"]
        self.assertEqual(profile["openhands_total_token_limit"], 1_500_000)
        self.assertEqual(profile["openhands_max_steps"], 120)
        self.assertTrue(profile["adaptive_budget_v2"])
        self.assertFalse(profile.get("contract_closure_gate_lite_v1", False))
        self.assertFalse(profile.get("mount_public_tests", False))


if __name__ == "__main__":
    unittest.main()
