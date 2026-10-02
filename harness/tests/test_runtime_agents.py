from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_adapters import AgentRunContext
from featureliftbench.agent_adapters import SUPPORTED_AGENTS
from featureliftbench.agent_adapters import get_agent_adapter
from featureliftbench.agent_config import load_agent_run_config
from featureliftbench.agent_docker import build_agent_docker_invocation
from featureliftbench.runtime_agents import RUNTIME_TASK_FILENAME
from featureliftbench.runtime_agents import build_codex_command
from featureliftbench.runtime_agents import build_deepseek_harness_command
from featureliftbench.runtime_agents import load_runtime_pins
from featureliftbench.runtime_agents import resolve_runtime_binary
from featureliftbench.runtime_agents import write_runtime_task_file
from featureliftbench.runtime_install import _codex_release_asset


class RuntimeAgentTests(unittest.TestCase):
    def test_pins_are_complete_hex_shas(self) -> None:
        pins = load_runtime_pins()
        self.assertEqual(pins["schema"], "featureliftbench.runtime_pins.v1")
        dsh = pins["runtimes"]["deepseek-harness"]
        codex = pins["runtimes"]["codex"]
        for spec in (dsh, codex):
            self.assertRegex(spec["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(spec["tag"])
            self.assertTrue(spec["repository"].endswith(".git"))
            self.assertTrue(spec["npm_package"])
            self.assertTrue(spec["npm_version"])
        self.assertEqual(dsh["npm_package"], "@deepseek-ai/dsh")
        self.assertEqual(codex["github_release_tag"], "rust-v0.149.0")

    def test_adapters_are_registered(self) -> None:
        self.assertIn("deepseek-harness", SUPPORTED_AGENTS)
        self.assertIn("codex", SUPPORTED_AGENTS)
        self.assertEqual(get_agent_adapter("dsh").name, "deepseek-harness")
        self.assertEqual(get_agent_adapter("codex-cli").name, "codex")

    def test_prepare_writes_main_boundary_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            context = AgentRunContext(
                workspace_dir=workspace,
                task_file=workspace / "TASK.md",
                submission_dir=workspace / "submission",
                agent_output_dir=Path(tmp) / "agent",
                task_text="Extract Widget from repo/.",
            )
            path = write_runtime_task_file(context)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(path.name, RUNTIME_TASK_FILENAME)
            self.assertIn("hidden_tests/", text)
            self.assertIn("featurelifted/", text)
            self.assertIn("Extract Widget from repo/.", text)
            self.assertNotIn("reference_solution", text.lower())

    def test_deepseek_harness_headless_command(self) -> None:
        context = AgentRunContext(
            workspace_dir=Path("/tmp/ws"),
            task_file=Path("/tmp/ws/TASK.md"),
            submission_dir=Path("/tmp/ws/submission"),
            agent_output_dir=Path("/tmp/agent"),
            task_text="task",
        )
        config = AgentRunConfig(
            agent="deepseek-harness",
            agent_bin="/opt/dsh",
            extra_args=("--quiet",),
        )
        command = build_deepseek_harness_command(context, config)
        self.assertEqual(command[0], "/opt/dsh")
        self.assertEqual(command[1:3], ["--profile", "headless"])
        self.assertIn("--quiet", command)
        self.assertTrue(command[-1].startswith("Follow FEATURELIFT_AGENT_TASK.md"))

    def test_codex_noninteractive_command(self) -> None:
        context = AgentRunContext(
            workspace_dir=Path("/tmp/ws"),
            task_file=Path("/tmp/ws/TASK.md"),
            submission_dir=Path("/tmp/ws/submission"),
            agent_output_dir=Path("/tmp/agent"),
            task_text="task",
        )
        config = AgentRunConfig(
            agent="codex",
            model="gpt-5",
            env={"FEATURELIFTBENCH_CODEX_BIN": "/opt/codex"},
        )
        command = build_codex_command(context, config)
        self.assertEqual(
            command[:5],
            [
                "/opt/codex",
                "exec",
                "--approve-for-me",
                "--skip-git-repo-check",
                "--json",
            ],
        )
        self.assertIn("--model", command)
        self.assertIn("gpt-5", command)

    def test_docker_inner_command_uses_container_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            agent_output = Path(tmp) / "agent"
            workspace.mkdir()
            agent_output.mkdir()
            context = AgentRunContext(
                workspace_dir=workspace,
                task_file=workspace / "TASK.md",
                submission_dir=workspace / "submission",
                agent_output_dir=agent_output,
                task_text="Solve this task",
            )
            config = AgentRunConfig(agent="deepseek-harness", agent_bin="dsh")
            invocation = build_agent_docker_invocation(context, config)
            joined = " ".join(invocation.command)
            self.assertIn("/usr/local/bin/dsh", invocation.command)
            self.assertIn("--profile", invocation.command)
            self.assertIn("FEATURELIFT_AGENT_TASK.md", joined)

    def test_example_runtime_profiles_are_main_boundary(self) -> None:
        config_file = (
            Path(__file__).resolve().parents[1] / "config" / "agents.example.toml"
        )
        for agent, profile in (
            ("deepseek-harness", "dsh_deepseek_v4_flash_main"),
            ("codex", "codex_gpt_main"),
        ):
            loaded = load_agent_run_config(
                base_config=AgentRunConfig(agent=agent),
                config_path=config_file,
                profile_name=profile,
            )
            self.assertEqual(loaded.summary["ablation_arm"], "main")
            self.assertFalse(loaded.summary["expose_source_hints"])
            self.assertFalse(loaded.summary["mount_public_tests"])
            self.assertEqual(loaded.summary["prompt_style"], "standard")
            self.assertEqual(loaded.summary["source_context"], "full_repository")
            self.assertFalse(Path(str(loaded.run_config.agent_bin or "")).is_absolute())

    def test_core12_slice_has_twelve_ids(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "config"
            / "experiments"
            / "runtime_ablation_core12_v1.txt"
        )
        ids = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)


    def test_docker_inner_command_rewrites_host_binary_to_path_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            agent_output = Path(tmp) / "agent"
            workspace.mkdir()
            agent_output.mkdir()
            context = AgentRunContext(
                workspace_dir=workspace,
                task_file=workspace / "TASK.md",
                submission_dir=workspace / "submission",
                agent_output_dir=agent_output,
                task_text="Solve this task",
            )
            config = AgentRunConfig(
                agent="deepseek-harness",
                agent_bin="/host/opt/dsh",
            )
            invocation = build_agent_docker_invocation(context, config)
            self.assertIn("/usr/local/bin/dsh", invocation.command)
            self.assertNotIn("/host/opt/dsh", invocation.command)

    def test_absolute_agent_bin_wins(self) -> None:
        config = AgentRunConfig(agent="deepseek-harness", agent_bin="/opt/custom-dsh")
        self.assertEqual(
            resolve_runtime_binary(
                config, env_name="FEATURELIFTBENCH_DSH_BIN", default="dsh"
            ),
            "/opt/custom-dsh",
        )

    def test_bare_name_prefers_repo_local_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "dsh"
            local.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            local.chmod(0o755)
            config = AgentRunConfig(agent="deepseek-harness", agent_bin="dsh")
            with mock.patch.dict(os.environ, {"FEATURELIFTBENCH_RUNTIME_BIN_DIR": tmp}):
                resolved = resolve_runtime_binary(
                    config, env_name="FEATURELIFTBENCH_DSH_BIN", default="dsh"
                )
            self.assertEqual(Path(resolved).resolve(), local.resolve())

    def test_codex_release_asset_mapping(self) -> None:
        self.assertEqual(
            _codex_release_asset(system="Darwin", machine="arm64"),
            "codex-aarch64-apple-darwin.tar.gz",
        )
        self.assertEqual(
            _codex_release_asset(system="Linux", machine="x86_64"),
            "codex-x86_64-unknown-linux-musl.tar.gz",
        )


if __name__ == "__main__":
    unittest.main()
