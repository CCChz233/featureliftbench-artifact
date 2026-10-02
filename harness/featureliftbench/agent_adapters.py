"""Agent adapter implementations for FeatureLiftBench runs."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .active_agent_processes import register_process
from .active_agent_processes import terminate_active_agent_processes
from .active_agent_processes import unregister_process
from .paths import HARNESS_ROOT
from .resource_limits import apply_agent_memory_limit


@dataclass(frozen=True)
class AgentRunContext:
    """Paths and prompt content passed to an agent adapter."""

    workspace_dir: Path
    task_file: Path
    submission_dir: Path
    agent_output_dir: Path
    task_text: str


@dataclass(frozen=True)
class AgentRunConfig:
    """User-configurable options for running an agent."""

    agent: str = "mini-swe-agent"
    agent_bin: str | None = None
    model: str | None = None
    config: str | None = None
    yolo: bool = False
    timeout_seconds: int = 3600
    step_limit: int = 0
    command: str | None = None
    extra_args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    profile: str = ""


@dataclass(frozen=True)
class AgentCommandResult:
    """Captured result from an agent subprocess."""

    name: str
    command: list[str]
    report_command: list[str]
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False
    reason: str = ""
    resource_limited: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    log_limit_exceeded: bool = False
    completion_detected: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def payload(self, *, stdout_log: Path | None = None, stderr_log: Path | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "command": self.report_command,
            "returncode": self.returncode,
            "passed": self.passed,
            "duration_seconds": round(self.duration_seconds, 6),
            "timed_out": self.timed_out,
            "reason": self.reason,
            "resource_limited": self.resource_limited,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "log_limit_exceeded": self.log_limit_exceeded,
            "completion_detected": self.completion_detected,
        }
        if stdout_log is not None:
            payload["stdout_log"] = str(stdout_log)
        if stderr_log is not None:
            payload["stderr_log"] = str(stderr_log)
        return payload


class AgentAdapter:
    """Base class for an agent command adapter."""

    name = "agent"
    close_stdin = False

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        raise NotImplementedError

    def prepare(self, context: AgentRunContext, config: AgentRunConfig) -> None:
        """Write adapter-specific files into the host workspace before launch."""

    def build_report_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        return self.build_command(context, config)

    def run(
        self,
        context: AgentRunContext,
        config: AgentRunConfig,
        *,
        stdout_log: Path | None = None,
        stderr_log: Path | None = None,
        completion_check: Callable[[], bool] | None = None,
    ) -> AgentCommandResult:
        self.prepare(context, config)
        command = self.build_command(context, config)
        report_command = self.build_report_command(context, config)
        env = os.environ.copy()
        if config.env:
            env.update(config.env)
        env.update(
            {
                "FEATURELIFTBENCH_WORKSPACE": str(context.workspace_dir),
                "FEATURELIFTBENCH_TASK_FILE": str(context.task_file),
                "FEATURELIFTBENCH_SUBMISSION_DIR": str(context.submission_dir),
                "FEATURELIFTBENCH_AGENT_OUTPUT_DIR": str(context.agent_output_dir),
                "PYTHONPATH": os.pathsep.join(
                    p for p in (env.get("PYTHONPATH", ""), str(HARNESS_ROOT)) if p
                ),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        command = apply_agent_memory_limit(command, env)

        start = time.monotonic()
        try:
            if (
                stdout_log is not None
                or stderr_log is not None
                or completion_check is not None
            ):
                return self._run_streaming(
                    command=command,
                    report_command=report_command,
                    cwd=context.workspace_dir,
                    env=env,
                    timeout_seconds=config.timeout_seconds,
                    start=start,
                    stdout_log=stdout_log,
                    stderr_log=stderr_log,
                    completion_check=completion_check,
                )
            completed = subprocess.run(
                command,
                cwd=context.workspace_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                check=False,
                stdin=subprocess.DEVNULL if self.close_stdin else None,
            )
        except FileNotFoundError as exc:
            return AgentCommandResult(
                name=self.name,
                command=command,
                report_command=report_command,
                returncode=127,
                duration_seconds=time.monotonic() - start,
                stdout="",
                stderr=str(exc),
                reason=f"agent executable not found: {command[0]}",
            )
        except subprocess.TimeoutExpired as exc:
            return AgentCommandResult(
                name=self.name,
                command=command,
                report_command=report_command,
                returncode=124,
                duration_seconds=time.monotonic() - start,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"agent timed out after {config.timeout_seconds}s",
                timed_out=True,
                reason=f"agent timed out after {config.timeout_seconds}s",
            )

        return AgentCommandResult(
            name=self.name,
            command=command,
            report_command=report_command,
            returncode=completed.returncode,
            duration_seconds=time.monotonic() - start,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _run_streaming(
        self,
        *,
        command: list[str],
        report_command: list[str],
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: int,
        start: float,
        stdout_log: Path | None,
        stderr_log: Path | None,
        completion_check: Callable[[], bool] | None,
    ) -> AgentCommandResult:
        if stdout_log is not None:
            stdout_log.parent.mkdir(parents=True, exist_ok=True)
        if stderr_log is not None:
            stderr_log.parent.mkdir(parents=True, exist_ok=True)

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL if self.close_stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            register_process(process)
        except FileNotFoundError as exc:
            return AgentCommandResult(
                name=self.name,
                command=command,
                report_command=report_command,
                returncode=127,
                duration_seconds=time.monotonic() - start,
                stdout="",
                stderr=str(exc),
                reason=f"agent executable not found: {command[0]}",
            )

        def pump(stream, log_path: Path | None, chunks: list[str]) -> None:
            assert stream is not None
            log_handle = log_path.open("w", encoding="utf-8") if log_path is not None else None
            try:
                for line in iter(stream.readline, ""):
                    chunks.append(line)
                    if log_handle is not None:
                        log_handle.write(line)
                        log_handle.flush()
            finally:
                if log_handle is not None:
                    log_handle.close()
                stream.close()

        threads = []
        if process.stdout is not None:
            threads.append(
                threading.Thread(
                    target=pump,
                    args=(process.stdout, stdout_log, stdout_chunks),
                    daemon=True,
                )
            )
        if process.stderr is not None:
            threads.append(
                threading.Thread(
                    target=pump,
                    args=(process.stderr, stderr_log, stderr_chunks),
                    daemon=True,
                )
            )
        for thread in threads:
            thread.start()

        try:
            deadline = start + timeout_seconds
            completion_check_error = ""
            while True:
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    returncode = process.wait(timeout=min(0.25, remaining))
                    break
                except subprocess.TimeoutExpired:
                    completion_detected = False
                    if completion_check is not None:
                        try:
                            completion_detected = completion_check()
                        except Exception as exc:  # Keep supervising the child.
                            completion_check_error = (
                                f"completion check failed: {type(exc).__name__}: {exc}"
                            )
                            completion_check = None
                    if completion_detected:
                        _kill_process_group(process)
                        process.wait(timeout=5)
                        for thread in threads:
                            thread.join(timeout=1)
                        return AgentCommandResult(
                            name=self.name,
                            command=command,
                            report_command=report_command,
                            returncode=0,
                            duration_seconds=time.monotonic() - start,
                            stdout="".join(stdout_chunks),
                            stderr="".join(stderr_chunks),
                            reason="validated completion artifact detected",
                            completion_detected=True,
                        )
                    if remaining <= 0:
                        _kill_process_group(process)
                        process.wait(timeout=5)
                        for thread in threads:
                            thread.join(timeout=1)
                        return AgentCommandResult(
                            name=self.name,
                            command=command,
                            report_command=report_command,
                            returncode=124,
                            duration_seconds=time.monotonic() - start,
                            stdout="".join(stdout_chunks),
                            stderr=(
                                "".join(stderr_chunks)
                                or f"agent timed out after {timeout_seconds}s"
                            )
                            + (
                                f"\n{completion_check_error}"
                                if completion_check_error
                                else ""
                            ),
                            timed_out=True,
                            reason=f"agent timed out after {timeout_seconds}s",
                        )

            for thread in threads:
                thread.join()
            return AgentCommandResult(
                name=self.name,
                command=command,
                report_command=report_command,
                returncode=returncode,
                duration_seconds=time.monotonic() - start,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
            )
        finally:
            unregister_process(process)


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except (PermissionError, OSError):
        process.kill()


class MiniSweAgentAdapter(AgentAdapter):
    """Adapter for the ``mini`` CLI from SWE-agent/mini-swe-agent."""

    name = "mini-swe-agent"

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        agent_bin = config.agent_bin or "mini"
        trajectory_path = context.agent_output_dir / "trajectory.json"
        if _use_live_trajectory_runner(agent_bin):
            command = [
                _mini_live_runner_python(agent_bin),
                "-m",
                "featureliftbench.mini_live_runner",
                "--task",
                context.task_text,
                "--output",
                str(trajectory_path),
                "--exit-immediately",
            ]
        else:
            command = [
                agent_bin,
                "--task",
                context.task_text,
                "--output",
                str(trajectory_path),
                "--exit-immediately",
            ]
        if config.model:
            command.extend(["--model", config.model])
        if config.config:
            command.extend(["--config", config.config])
        if config.yolo:
            command.append("--yolo")
        if config.step_limit > 0:
            command.extend(["--step-limit", str(config.step_limit)])
        command.extend(config.extra_args)
        return command

    def build_report_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        command = self.build_command(context, config)
        return ["@TASK.md" if item == context.task_text else item for item in command]


class CommandAgentAdapter(AgentAdapter):
    """Adapter for a user-provided command template."""

    name = "command"

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        if not config.command:
            raise ValueError("--agent-command is required when --agent command is used")
        rendered = config.command.format(
            workspace=context.workspace_dir,
            task_file=context.task_file,
            submission_dir=context.submission_dir,
            agent_output_dir=context.agent_output_dir,
        )
        command = shlex.split(rendered)
        command.extend(config.extra_args)
        return command


class FeatureLiftAgentAdapter(AgentAdapter):
    """Adapter for the FeatureLiftBench-native extraction agent controller."""

    name = "featurelift-agent"

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        command = _featurelift_agent_base_command(config.agent_bin)
        command.extend(
            [
                "run",
                "--workspace",
                str(context.workspace_dir),
                "--task-file",
                str(context.task_file),
                "--submission-dir",
                str(context.submission_dir),
                "--agent-output-dir",
                str(context.agent_output_dir),
            ]
        )
        if config.model:
            command.extend(["--model", config.model])
        command.extend(config.extra_args)
        return command


class DeepSeekHarnessAdapter(AgentAdapter):
    """Pinned DeepSeek Harness (`dsh --profile headless`) runtime ablation."""

    name = "deepseek-harness"

    def prepare(self, context: AgentRunContext, config: AgentRunConfig) -> None:
        from .runtime_agents import write_runtime_task_file

        del config
        write_runtime_task_file(context)

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        from .runtime_agents import build_deepseek_harness_command

        return build_deepseek_harness_command(context, config)


class CodexAdapter(AgentAdapter):
    """Pinned OpenAI Codex CLI (`codex exec`) runtime ablation."""

    name = "codex"
    close_stdin = True

    def prepare(self, context: AgentRunContext, config: AgentRunConfig) -> None:
        from .runtime_agents import write_runtime_task_file

        del config
        write_runtime_task_file(context)

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        from .runtime_agents import build_codex_command

        return build_codex_command(context, config)


class OpenHandsAgentAdapter(AgentAdapter):
    """Adapter for running OpenHands as the evaluated FeatureLiftBench agent."""

    name = "openhands-agent"

    def build_command(self, context: AgentRunContext, config: AgentRunConfig) -> list[str]:
        command = [
            sys.executable,
            "-m",
            "featureliftbench.openhands_runner",
            "run",
            "--workspace",
            str(context.workspace_dir),
            "--task-file",
            str(context.task_file),
            "--submission-dir",
            str(context.submission_dir),
            "--agent-output-dir",
            str(context.agent_output_dir),
            "--timeout-seconds",
            str(max(1, int(config.timeout_seconds) - 10)),
        ]
        if config.model:
            command.extend(["--model", config.model])
        if config.command:
            command.extend(["--openhands-command", config.command])
        command.extend(config.extra_args)
        return command


def _featurelift_agent_base_command(agent_bin: str | None) -> list[str]:
    if agent_bin:
        return [agent_bin]
    return [sys.executable, "-m", "featureliftbench.featurelift_agent"]


def _use_live_trajectory_runner(agent_bin: str) -> bool:
    """Use in-process mini runner that snapshots trajectory.json after each step."""

    if os.environ.get("FEATURELIFTBENCH_LIVE_TRAJECTORY", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    normalized = Path(agent_bin).name
    return normalized in {"mini", "mini-swe-agent"}


def _mini_live_runner_python(agent_bin: str) -> str:
    """Use the Python environment that owns an absolute mini executable.

    ``mini_live_runner`` imports ``minisweagent`` directly. Profiles commonly
    point at a conda/venv ``bin/mini`` while FeatureLiftBench itself runs under
    another interpreter, so using ``sys.executable`` can make the wrapper fail
    before the Agent starts. Bare executable names retain the old behavior for
    Docker command normalization and PATH-based installs.
    """

    path = Path(agent_bin)
    if path.is_absolute():
        for name in ("python", "python3"):
            candidate = path.parent / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return sys.executable


def get_agent_adapter(name: str) -> AgentAdapter:
    """Return an adapter for a supported agent name."""

    normalized = name.strip().lower().replace("_", "-")
    if normalized in {"mini", "mini-swe-agent", "minisweagent"}:
        return MiniSweAgentAdapter()
    if normalized in {"featurelift-agent", "featureliftagent", "featurelift"}:
        return FeatureLiftAgentAdapter()
    if normalized in {"openhands", "openhands-agent", "openhandsagent"}:
        return OpenHandsAgentAdapter()
    if normalized in {"deepseek-harness", "deepseekharness", "dsh"}:
        return DeepSeekHarnessAdapter()
    if normalized in {"codex", "codex-cli", "openai-codex"}:
        return CodexAdapter()
    if normalized in {"command", "custom"}:
        return CommandAgentAdapter()
    raise ValueError(f"unsupported agent: {name}")


SUPPORTED_AGENTS = (
    "mini-swe-agent",
    "featurelift-agent",
    "openhands-agent",
    "deepseek-harness",
    "codex",
    "command",
)
