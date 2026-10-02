"""Contract-only supplementary arm. Official Main behavior must stay unchanged."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_adapters import AgentRunContext
from featureliftbench.agent_docker import build_agent_docker_invocation
from featureliftbench.agent_runner import build_task_prompt
from featureliftbench.agent_runner import prepare_agent_workspace
from featureliftbench.metadata import load_metadata
from featureliftbench.openhands_runner import OpenHandsRunnerConfig
from featureliftbench.openhands_runner import _build_openhands_prompt
from featureliftbench.paths import HARNESS_ROOT
from featureliftbench.source_ablation import HARNESS_MOUNT_ENV
from featureliftbench.source_ablation import ISOLATION_ENV
from featureliftbench.source_ablation import agent_harness_mount_mode
from featureliftbench.source_ablation import agent_source_available
from featureliftbench.source_ablation import experiment_condition_fields
from featureliftbench.source_ablation import render_contract_only_agent_workspace_task
from featureliftbench.task_render import render_agent_workspace_task


class SourceAblationOptionsTests(unittest.TestCase):
    def test_main_defaults_are_unchanged(self) -> None:
        options = AblationOptions()
        self.assertEqual(options.ablation_arm, "main")
        self.assertEqual(options.source_context, "full_repository")
        self.assertTrue(agent_source_available(options))
        self.assertEqual(experiment_condition_fields(options, {}), {})
        self.assertNotIn("agent_source_available", options.summary())

    def test_contract_only_is_a_distinct_arm(self) -> None:
        options = AblationOptions(source_context="contract_only")
        self.assertEqual(options.ablation_arm, "contract_only")
        self.assertFalse(agent_source_available(options))
        extra = experiment_condition_fields(options, {})
        self.assertEqual(extra["agent_source_available"], False)
        self.assertEqual(extra["agent_harness_mount"], "package")
        self.assertFalse(extra["source_ablation_isolation"])

    def test_isolation_env_records_on_full_arm(self) -> None:
        options = AblationOptions()
        extra = experiment_condition_fields(options, {ISOLATION_ENV: "1"})
        self.assertTrue(extra["agent_source_available"])
        self.assertTrue(extra["source_ablation_isolation"])
        self.assertEqual(extra["agent_harness_mount"], "package")

    def test_contract_only_rejects_source_hints(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            AblationOptions(source_context="contract_only", expose_source_hints=True)

    def test_cli_contract_only_does_not_change_main_resolution(self) -> None:
        main = resolve_ablation_options()
        contract = resolve_ablation_options(source_context="contract_only")
        self.assertEqual(main.ablation_arm, "main")
        self.assertEqual(contract.ablation_arm, "contract_only")
        self.assertEqual(main.source_context, "full_repository")


class SourceAblationWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "sanity"
            / "iniconfig__parse_config__001"
        )
        self.metadata = load_metadata(self.task_dir).data
        self.compliant_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )

    def test_main_workspace_still_materializes_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(),
            )
            self.assertTrue((workspace / "repo").exists())
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertIn("repo/", prompt)

    def test_contract_only_workspace_omits_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(source_context="contract_only"),
            )
            self.assertFalse((workspace / "repo").exists())
            self.assertFalse((workspace / "public_tests").exists())
            self.assertFalse((workspace / "hidden_tests").exists())
            self.assertTrue((workspace / "TASK.md").is_file())
            self.assertTrue((workspace / "metadata.json").is_file())
            self.assertTrue((workspace / "requirements.lock").is_file())
            self.assertTrue((workspace / "submission").is_dir())
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertIn("not available", prompt.lower())
            self.assertNotIn("search `repo/`", prompt)
            self.assertNotIn("inspect upstream tests, documentation, and examples that exist under `repo/`", prompt)

    def test_compliant_contract_only_prompt_keeps_api_drops_repo_instructions(self) -> None:
        metadata = load_metadata(self.compliant_dir).data
        main = render_agent_workspace_task(metadata)
        contract = render_contract_only_agent_workspace_task(metadata)
        self.assertIn("## Target API", main)
        self.assertIn("## Target API", contract)
        self.assertIn("inspecting the full upstream repository", main)
        self.assertNotIn("inspecting the full upstream repository", contract)
        self.assertIn("The upstream source repository is not available", contract)
        self.assertIn("inspect upstream tests, documentation, and examples that exist under `repo/`", main)
        self.assertNotIn("inspect upstream tests, documentation, and examples that exist under `repo/`", contract)
        self.assertIn("from featurelifted import", main)
        self.assertIn("from featurelifted import", contract)

    def test_legacy_prompt_contract_only_does_not_tell_agent_to_copy_repo(self) -> None:
        prompt = build_task_prompt(
            self.metadata,
            ablation=AblationOptions(source_context="contract_only"),
        )
        self.assertNotIn("Copy the smallest **behavior-complete** implementation closure from `repo/`", prompt)
        self.assertIn("Required Output API", prompt)
        self.assertIn("The upstream source repository is not available", prompt)


class SourceAblationDockerTests(unittest.TestCase):
    def _context(self, root: Path) -> tuple[AgentRunContext, Path]:
        workspace = root / "workspace"
        agent_output = root / "agent"
        workspace.mkdir()
        agent_output.mkdir()
        context = AgentRunContext(
            workspace_dir=workspace,
            task_file=workspace / "TASK.md",
            submission_dir=workspace / "submission",
            agent_output_dir=agent_output,
            task_text="Solve this task",
        )
        return context, agent_output

    def test_default_docker_still_mounts_full_harness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, _ = self._context(Path(tmp))
            config = AgentRunConfig(agent="mini-swe-agent", yolo=True)
            with mock.patch.dict(os.environ, {ISOLATION_ENV: "", HARNESS_MOUNT_ENV: ""}, clear=False):
                invocation = build_agent_docker_invocation(context, config)
            joined = " ".join(invocation.command)
            self.assertIn(f"{HARNESS_ROOT.resolve()}:/flb/harness:ro", joined)
            self.assertNotIn(
                f"{(HARNESS_ROOT / 'featureliftbench').resolve()}:/flb/harness/featureliftbench:ro",
                joined,
            )
            self.assertNotIn("--tmpfs /flb/harness:", joined)
            self.assertNotIn("pypi.org:127.0.0.1", joined)

    def test_isolation_mounts_package_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context, _ = self._context(Path(tmp))
            config = AgentRunConfig(
                agent="mini-swe-agent",
                env={ISOLATION_ENV: "1"},
                yolo=True,
            )
            invocation = build_agent_docker_invocation(context, config)
            joined = " ".join(invocation.command)
            self.assertIn(
                f"{(HARNESS_ROOT / 'featureliftbench').resolve()}:/flb/harness/featureliftbench:ro",
                joined,
            )
            self.assertIn("--tmpfs /flb/harness:rw,nosuid,nodev,mode=755", joined)
            self.assertNotIn(f"{HARNESS_ROOT.resolve()}:/flb/harness:ro", joined)
            self.assertIn("--add-host pypi.org:127.0.0.1", joined)

    def test_mount_mode_default_is_full(self) -> None:
        self.assertEqual(agent_harness_mount_mode({}), "full")
        self.assertEqual(
            agent_harness_mount_mode({"FEATURELIFTBENCH_SOURCE_CONTEXT": "full_repository"}),
            "full",
        )


class SourceAblationOpenHandsPromptTests(unittest.TestCase):
    def test_wrapper_main_still_points_at_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "TASK.md"
            task.write_text("# task\n", encoding="utf-8")
            config = OpenHandsRunnerConfig(
                workspace_dir=root,
                task_file=task,
                submission_dir=root / "submission",
                agent_output_dir=root / "agent",
                model="test-model",
            )
            with mock.patch.dict(os.environ, {"FEATURELIFTBENCH_SOURCE_CONTEXT": "full_repository"}):
                text = _build_openhands_prompt(config)
            self.assertIn("Source code to inspect is under `repo/`.", text)
            self.assertIn("already present under `repo/`", text)

    def test_wrapper_contract_only_omits_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "TASK.md"
            task.write_text("# task\n", encoding="utf-8")
            config = OpenHandsRunnerConfig(
                workspace_dir=root,
                task_file=task,
                submission_dir=root / "submission",
                agent_output_dir=root / "agent",
                model="test-model",
            )
            env = {
                "FEATURELIFTBENCH_SOURCE_CONTEXT": "contract_only",
                "FEATURELIFTBENCH_MOUNT_PUBLIC_TESTS": "0",
                "FEATURELIFTBENCH_EXPOSE_SOURCE_HINTS": "0",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                text = _build_openhands_prompt(config)
            self.assertNotIn("Source code to inspect is under `repo/`.", text)
            self.assertIn("source repository is not present", text.lower())
            self.assertNotIn("Implement from the public contract and `repo/`.", text)
