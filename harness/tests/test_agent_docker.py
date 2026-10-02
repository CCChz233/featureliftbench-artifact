from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_adapters import AgentRunContext
from featureliftbench.agent_docker import build_agent_docker_invocation
from featureliftbench.agent_docker import run_agent_in_docker
from featureliftbench.agent_docker import _should_mirror_agent_logs
from featureliftbench.paths import HARNESS_ROOT
from featureliftbench.repo_graph.policy import MODE_ENV as REPO_GRAPH_MODE_ENV
from featureliftbench.repo_graph.policy import ROOT_ENV as REPO_GRAPH_ROOT_ENV


class _FakeDockerProcess:
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int | None = 0,
    ) -> None:
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            self.returncode = -9
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class AgentDockerTests(unittest.TestCase):
    def test_enabled_repo_graph_uses_private_container_run_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            agent_output.mkdir()
            context = AgentRunContext(
                workspace_dir=workspace,
                task_file=workspace / "TASK.md",
                submission_dir=workspace / "submission",
                agent_output_dir=agent_output,
                task_text="graph task",
            )
            config = AgentRunConfig(
                agent="mini-swe-agent",
                env={
                    REPO_GRAPH_MODE_ENV: "static",
                    REPO_GRAPH_ROOT_ENV: str(agent_output / "state" / "repo_graph"),
                },
            )
            invocation = build_agent_docker_invocation(context, config)
            self.assertEqual(
                invocation.env[REPO_GRAPH_ROOT_ENV],
                "/flb/agent/state/repo_graph",
            )
            self.assertIn(f"--env {REPO_GRAPH_ROOT_ENV}", " ".join(invocation.command))

    def test_builds_bounded_docker_command_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="mini-swe-agent",
                env={
                    "OPENAI_API_KEY": "sk-secret-value",
                    "OPENAI_BASE_URL": "https://api.example.test/v1",
                },
                yolo=True,
            )

            invocation = build_agent_docker_invocation(
                context,
                config,
                image="featureliftbench-agent:test",
            )

            command = invocation.command
            joined = " ".join(command)
            self.assertEqual(command[:3], ["docker", "run", "--rm"])
            self.assertIn("--network", command)
            self.assertIn("bridge", command)
            self.assertIn("--memory", command)
            self.assertIn("8g", command)
            self.assertIn("--pids-limit", command)
            self.assertIn("512", command)
            self.assertIn("--cap-drop", command)
            self.assertIn("ALL", command)
            self.assertIn("--security-opt", command)
            self.assertIn("no-new-privileges", command)
            self.assertIn(f"{workspace.resolve()}:/flb/workspace:rw", joined)
            self.assertIn(f"{agent_output.resolve()}:/flb/agent:rw", joined)
            self.assertIn(f"{HARNESS_ROOT.resolve()}:/flb/harness:ro", joined)
            self.assertIn("--env OPENAI_API_KEY", joined)
            self.assertNotIn("sk-secret-value", joined)
            self.assertNotIn(f"{Path.home()}:/", joined)
            self.assertNotIn(".env", joined)
            self.assertNotIn("/var/run/docker.sock", joined)
            self.assertIn("python -m featureliftbench.mini_live_runner", joined)
            self.assertEqual(invocation.env["OPENAI_API_KEY"], "sk-secret-value")
            self.assertEqual(invocation.env["PYTHONPATH"], "/flb/harness")
            self.assertEqual(invocation.env["HOME"], "/tmp/flb-home")
            self.assertEqual(invocation.env["PYTHONUNBUFFERED"], "1")

    def test_openhands_agent_docker_uses_harness_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="openhands-agent",
                model="deepseek/deepseek-v4-flash",
                command="openhands run --prompt-file {prompt_file}",
            )

            invocation = build_agent_docker_invocation(
                context,
                config,
                image="featureliftbench-agent:test",
            )

            joined = " ".join(invocation.command)
            self.assertIn("python -m featureliftbench.openhands_runner", joined)
            self.assertIn("--workspace /flb/workspace", joined)
            self.assertIn("--submission-dir /flb/workspace/submission", joined)
            self.assertIn("--agent-output-dir /flb/agent", joined)
            self.assertIn("deepseek/deepseek-v4-flash", joined)
            self.assertIn("openhands run --prompt-file {prompt_file}", joined)

    def test_agent_docker_env_overrides_resource_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(agent="command", command="python -c 'pass'")

            with mock.patch.dict(
                os.environ,
                {
                    "FEATURELIFTBENCH_AGENT_DOCKER_NETWORK": "none",
                    "FEATURELIFTBENCH_AGENT_DOCKER_MEMORY": "2g",
                    "FEATURELIFTBENCH_AGENT_DOCKER_CPUS": "1",
                    "FEATURELIFTBENCH_AGENT_DOCKER_PIDS": "64",
                    "FEATURELIFTBENCH_AGENT_DOCKER_TMPFS": "/tmp:rw,size=256m",
                },
            ):
                invocation = build_agent_docker_invocation(context, config)

            command = invocation.command
            self.assertEqual(command[command.index("--network") + 1], "none")
            self.assertEqual(command[command.index("--memory") + 1], "2g")
            self.assertEqual(command[command.index("--cpus") + 1], "1")
            self.assertEqual(command[command.index("--pids-limit") + 1], "64")
            self.assertEqual(command[command.index("--tmpfs") + 1], "/tmp:rw,size=256m")

    def test_command_agent_uses_container_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="command",
                command="python -c 'from pathlib import Path; Path(\"{submission_dir}\").mkdir()'",
            )

            invocation = build_agent_docker_invocation(context, config)

            joined = " ".join(invocation.command)
            self.assertIn("/flb/workspace/submission", joined)
            self.assertNotIn(str(workspace / "submission"), joined)

    def test_timeout_kills_container_and_returns_timed_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="command",
                command="python -c 'import time; time.sleep(60)'",
                timeout_seconds=1,
            )

            fake_process = _FakeDockerProcess(
                stdout=b"partial out",
                stderr=b"partial err",
                returncode=None,
            )
            with mock.patch(
                "featureliftbench.agent_docker.subprocess.Popen",
                return_value=fake_process,
            ):
                with mock.patch("featureliftbench.agent_docker._kill_container") as kill_mock:
                    result = run_agent_in_docker(context, config)

            self.assertTrue(result.timed_out)
            self.assertEqual(result.returncode, 124)
            self.assertEqual(result.stdout, "partial out")
            self.assertEqual(result.stderr, "partial err")
            kill_mock.assert_called_once()

    def test_log_limit_truncates_and_kills_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="command",
                command="python -c 'print(\"x\")'",
                timeout_seconds=30,
            )
            fake_process = _FakeDockerProcess(stdout=b"x" * 10000, returncode=None)

            with mock.patch.dict(os.environ, {"FEATURELIFTBENCH_COMMAND_OUTPUT_LIMIT_BYTES": "1024"}):
                with mock.patch(
                    "featureliftbench.agent_docker.subprocess.Popen",
                    return_value=fake_process,
                ):
                    with mock.patch("featureliftbench.agent_docker._kill_container") as kill_mock:
                        result = run_agent_in_docker(
                            context,
                            config,
                            stdout_log=agent_output / "stdout.log",
                            stderr_log=agent_output / "stderr.log",
                        )

            self.assertTrue(result.log_limit_exceeded)
            self.assertTrue(result.stdout_truncated)
            self.assertFalse(result.resource_limited)
            self.assertLessEqual(len(result.stdout.encode("utf-8")), 1024)
            self.assertIn("output exceeded log limit", result.reason)
            kill_mock.assert_called_once()

    def test_agent_logs_redact_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="command",
                command="python -c 'print(\"ok\")'",
                env={"OPENAI_API_KEY": "sk-secret-value"},
            )
            fake_process = _FakeDockerProcess(
                stdout=b"token=sk-secret-value\n",
                stderr=b"err sk-secret-value\n",
                returncode=0,
            )

            with mock.patch(
                "featureliftbench.agent_docker.subprocess.Popen",
                return_value=fake_process,
            ):
                result = run_agent_in_docker(
                    context,
                    config,
                    stdout_log=agent_output / "stdout.log",
                    stderr_log=agent_output / "stderr.log",
                )

            self.assertNotIn("sk-secret-value", result.stdout)
            self.assertNotIn("sk-secret-value", result.stderr)
            self.assertNotIn(
                "sk-secret-value",
                (agent_output / "stdout.log").read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "sk-secret-value",
                (agent_output / "stderr.log").read_text(encoding="utf-8"),
            )
            self.assertIn("[REDACTED]", result.stdout)
            self.assertIn("[REDACTED]", result.stderr)

    def test_pump_stream_writes_stdout_log_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="command",
                command="python -c 'print(\"ok\")'",
            )
            stdout_log = agent_output / "stdout.log"
            fake_process = _FakeDockerProcess(stdout=b"line one\nline two\n", returncode=0)

            with mock.patch(
                "featureliftbench.agent_docker.subprocess.Popen",
                return_value=fake_process,
            ):
                run_agent_in_docker(
                    context,
                    config,
                    stdout_log=stdout_log,
                    stderr_log=agent_output / "stderr.log",
                )

            self.assertEqual(stdout_log.read_text(encoding="utf-8"), "line one\nline two\n")

    def test_mirror_writes_redacted_output_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            config = AgentRunConfig(
                agent="command",
                command="python -c 'print(\"ok\")'",
                env={"OPENAI_API_KEY": "sk-secret-value"},
            )
            fake_process = _FakeDockerProcess(
                stdout=b"token=sk-secret-value\n",
                returncode=0,
            )
            stderr_capture = io.StringIO()

            with mock.patch(
                "featureliftbench.agent_docker._should_mirror_agent_logs",
                return_value=True,
            ):
                with mock.patch("featureliftbench.agent_docker.sys.stderr", stderr_capture):
                    with mock.patch(
                        "featureliftbench.agent_docker.subprocess.Popen",
                        return_value=fake_process,
                    ):
                        run_agent_in_docker(
                            context,
                            config,
                            stdout_log=agent_output / "stdout.log",
                            stderr_log=agent_output / "stderr.log",
                        )

            mirrored = stderr_capture.getvalue()
            self.assertIn("[REDACTED]", mirrored)
            self.assertNotIn("sk-secret-value", mirrored)

    def test_should_mirror_agent_logs_respects_env_override(self) -> None:
        with mock.patch("featureliftbench.agent_docker.sys.stderr.isatty", return_value=True):
            with mock.patch.dict(os.environ, {"FEATURELIFTBENCH_AGENT_LOG_MIRROR": "0"}):
                self.assertFalse(_should_mirror_agent_logs())
            with mock.patch.dict(os.environ, {"FEATURELIFTBENCH_AGENT_LOG_MIRROR": "1"}):
                self.assertTrue(_should_mirror_agent_logs())


if __name__ == "__main__":
    unittest.main()
