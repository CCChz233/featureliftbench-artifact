"""Tests for TD-Cognition two-phase protocol."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.agent_runner import prepare_agent_workspace
from featureliftbench.metadata import load_metadata
from featureliftbench.td_cognition import evaluate_phase1_artifacts
from featureliftbench.td_cognition import prepare_phase2_workspace
from featureliftbench.td_cognition import validate_cognition_scaffold
from featureliftbench.td_cognition import validate_probes


def _filled_cognition_numbered() -> str:
    return (
        "# Cognition\n\n"
        "## Critical Use Cases\n\n"
        "1. Parse empty config returns empty mapping\n"
        "2. Duplicate keys follow documented precedence\n"
        "3. Invalid syntax raises a clear error\n\n"
        "## Required Surface\n\n"
        "- parse API\n\n"
        "## Support Set Hypothesis\n\n"
        "- iniconfig core modules\n\n"
        "## Exclusions\n\n"
        "- unrelated packaging helpers\n\n"
        "## Probes\n\n"
        "- probes/test_contract_smoke.py\n"
    )


class TdCognitionAblationTests(unittest.TestCase):
    def test_arm_name(self) -> None:
        self.assertEqual(AblationOptions(td_cognition=True).ablation_arm, "td_cognition")

    def test_resolve_from_profile(self) -> None:
        options = resolve_ablation_options(profile={"td_cognition": True})
        self.assertTrue(options.td_cognition)
        self.assertEqual(options.ablation_arm, "td_cognition")


class TdCognitionTwoPhaseWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "sanity"
            / "iniconfig__parse_config__001"
        )
        self.metadata = load_metadata(self.task_dir).data

    def test_phase1_keeps_writable_submission_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(td_cognition=True),
            )
            submission = workspace / "submission"
            self.assertTrue(submission.is_dir())
            self.assertTrue((workspace / "COGNITION.md").is_file())
            self.assertTrue((workspace / "probes").is_dir())
            task = (workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertIn("Phase 1", task)
            self.assertIn("Do not", task)
            self.assertIn("import submission", task)

            blocked = evaluate_phase1_artifacts(workspace, run_pytest=False)
            self.assertFalse(blocked.ok)

            (workspace / "COGNITION.md").write_text(
                _filled_cognition_numbered(),
                encoding="utf-8",
            )
            self.assertTrue(validate_cognition_scaffold(workspace).ok)
            (workspace / "probes" / "test_contract_smoke.py").write_text(
                "def test_truth() -> None:\n    assert True\n",
                encoding="utf-8",
            )
            # Prefer docker-backed gate (production path). Mock the helper so
            # hosts without the agent image still exercise wiring.
            fake = mock.Mock(
                returncode=0,
                stdout=".\n",
                stderr="",
                timed_out=False,
                command=["docker", "run"],
                container_name="flb-gate-test",
            )
            with mock.patch(
                "featureliftbench.agent_docker.run_command_in_agent_docker",
                return_value=fake,
            ):
                ok = evaluate_phase1_artifacts(
                    workspace,
                    run_pytest=True,
                    pytest_backend="docker",
                    docker_image="featureliftbench-agent:latest",
                )
            self.assertTrue(ok.ok, ok.errors)

            phase2 = prepare_phase2_workspace(
                workspace,
                (workspace / "TASK.md").read_text(encoding="utf-8"),
            )
            self.assertIn("Phase 2", phase2)
            self.assertIn("Parse empty config", phase2)
            self.assertTrue((workspace / "submission").is_dir())
            self.assertFalse(any((workspace / "submission").iterdir()))


class TdCognitionScaffoldParseTests(unittest.TestCase):
    def _write(self, workspace: Path, cognition: str) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "COGNITION.md").write_text(cognition, encoding="utf-8")

    def test_accepts_uc_heading_and_bullet_use_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write(
                workspace,
                "# Cognition\n\n"
                "## Use Cases\n\n"
                "### UC1 happy path parse\n\n"
                "### UC2 duplicate key precedence\n\n"
                "### UC3 invalid syntax error\n\n"
                "## Required Surface\n\n- api\n\n"
                "## Support Set Hypothesis\n\n- mod\n\n"
                "## Exclusions\n\n- other\n\n"
                "## Probes\n\n- probes/a.py\n",
            )
            result = validate_cognition_scaffold(workspace)
            self.assertTrue(result.ok, result.errors)
            self.assertGreaterEqual(result.details["use_case_count"], 3)

    def test_accepts_bullet_list_use_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write(
                workspace,
                "# Cognition\n\n"
                "## Critical Use Cases\n\n"
                "- first concrete case\n"
                "- second concrete case\n"
                "- third concrete case\n\n"
                "## Required Surface\n\n- api\n\n"
                "## Support Set Hypothesis\n\n- mod\n\n"
                "## Exclusions\n\n- other\n\n"
                "## Probes\n\n- probes/a.py\n",
            )
            result = validate_cognition_scaffold(workspace)
            self.assertTrue(result.ok, result.errors)

    def test_rejects_unfilled_template_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            from featureliftbench.td_cognition import cognition_template

            self._write(workspace, cognition_template())
            result = validate_cognition_scaffold(workspace)
            self.assertFalse(result.ok)
            self.assertTrue(any("placeholder" in e for e in result.errors))


class TdCognitionProbeGateTests(unittest.TestCase):
    def test_bans_submission_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "COGNITION.md").write_text(
                _filled_cognition_numbered(), encoding="utf-8"
            )
            probes = workspace / "probes"
            probes.mkdir()
            (probes / "__init__.py").write_text("", encoding="utf-8")
            (probes / "test_bad.py").write_text(
                "from submission.featurelifted import x\n\ndef test_x():\n    assert x\n",
                encoding="utf-8",
            )
            result = validate_probes(workspace, run_pytest=False)
            self.assertFalse(result.ok)
            self.assertTrue(any("import submission" in e for e in result.errors))

    def test_docker_backend_uses_agent_docker_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            probes = workspace / "probes"
            probes.mkdir()
            (probes / "__init__.py").write_text("", encoding="utf-8")
            (probes / "test_ok.py").write_text(
                "def test_truth() -> None:\n    assert True\n",
                encoding="utf-8",
            )
            fake = mock.Mock(
                returncode=0,
                stdout=".\n",
                stderr="",
                timed_out=False,
                command=["docker", "run"],
                container_name="flb-gate-test",
            )
            with mock.patch(
                "featureliftbench.agent_docker.run_command_in_agent_docker",
                return_value=fake,
            ) as mocked:
                result = validate_probes(
                    workspace,
                    run_pytest=True,
                    pytest_backend="docker",
                    docker_image="featureliftbench-agent:latest",
                )
            self.assertTrue(result.ok, result.errors)
            mocked.assert_called_once()
            args, kwargs = mocked.call_args
            self.assertEqual(Path(args[0]), workspace.resolve())
            self.assertEqual(
                args[1],
                ["python", "-m", "pytest", "probes/", "-q", "--tb=no"],
            )
            self.assertEqual(kwargs.get("image"), "featureliftbench-agent:latest")
            self.assertEqual(result.details.get("pytest_backend"), "docker")


if __name__ == "__main__":
    unittest.main()
