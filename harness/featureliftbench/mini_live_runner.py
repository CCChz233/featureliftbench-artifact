"""Run mini-swe-agent with incremental trajectory snapshots for live token progress."""

from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any

import typer
import yaml
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession
from rich.console import Console

from minisweagent import global_config_dir
from minisweagent.agents.default import DefaultAgent
from minisweagent.agents.default import LimitsExceeded
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.config import builtin_config_dir, get_config_path
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.run.extra.config import configure_if_first_time
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger

DEFAULT_CONFIG = Path(os.getenv("MSWEA_MINI_CONFIG_PATH", builtin_config_dir / "mini.yaml"))
DEFAULT_OUTPUT = global_config_dir / "last_mini_run.traj.json"
console = Console(highlight=False)
app = typer.Typer(rich_markup_mode="rich")
prompt_session = PromptSession(history=FileHistory(global_config_dir / "mini_task_history.txt"))


class LiveTrajectoryInteractiveAgent(InteractiveAgent):
    """Save trajectory after every step so harness progress can read token usage."""

    def __init__(self, *args: Any, trajectory_path: Path | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._trajectory_path = trajectory_path

    def step(self) -> dict:
        try:
            return super().step()
        finally:
            if self._trajectory_path is not None:
                save_traj(self, self._trajectory_path, print_path=False)

    def query(self) -> dict:
        """Use the non-interactive limit behavior in headless harness runs.

        ``InteractiveAgent.query`` asks for new limits after a limit is reached.
        Harness subprocesses have no stdin, so that prompt raises ``EOFError``
        and used to be misreported as a successful process exit.
        """

        if self.config.mode == "human":
            return super().query()
        return DefaultAgent.query(self)


@app.command()
def main(
    task: str = typer.Option(..., "-t", "--task", help="Task/problem statement"),
    model_name: str | None = typer.Option(None, "-m", "--model", help="Model to use"),
    model_class: str | None = typer.Option(None, "--model-class", help="Model class override"),
    yolo: bool = typer.Option(False, "-y", "--yolo", help="Run without confirmation"),
    cost_limit: float | None = typer.Option(None, "-l", "--cost-limit", help="Cost limit"),
    step_limit: int | None = typer.Option(None, "--step-limit", help="Agent step limit"),
    final_prompt: str | None = typer.Option(
        None,
        "--final-prompt",
        help="Prompt injected immediately before the final allowed model call",
    ),
    config_spec: Path = typer.Option(DEFAULT_CONFIG, "-c", "--config", help="Path to config file"),
    output: Path | None = typer.Option(DEFAULT_OUTPUT, "-o", "--output", help="Output trajectory file"),
    exit_immediately: bool = typer.Option(False, "--exit-immediately", help="Exit when agent finishes"),
) -> Any:
    configure_if_first_time()
    config_path = get_config_path(config_spec)
    console.print(f"Loading agent config from [bold green]'{config_path}'[/bold green]")
    config = yaml.safe_load(config_path.read_text())

    if yolo:
        config.setdefault("agent", {})["mode"] = "yolo"
    if cost_limit is not None:
        config.setdefault("agent", {})["cost_limit"] = cost_limit
    if step_limit is not None:
        config.setdefault("agent", {})["step_limit"] = max(0, step_limit)
    if final_prompt is not None:
        config.setdefault("agent", {})["final_prompt_template"] = final_prompt
    if exit_immediately:
        config.setdefault("agent", {})["confirm_exit"] = False
    if model_class is not None:
        config.setdefault("model", {})["model_class"] = model_class

    model = get_model(model_name, config.get("model", {}))
    env = LocalEnvironment(**config.get("env", {}))
    agent = LiveTrajectoryInteractiveAgent(
        model,
        env,
        trajectory_path=output,
        **config.get("agent", {}),
    )

    exit_status, result, extra_info = None, None, None
    unexpected_error = False
    try:
        exit_status, result = agent.run(task)  # type: ignore[arg-type]
    except Exception as exc:
        logger.error("Error running agent: %s", exc, exc_info=True)
        exit_status, result = type(exc).__name__, str(exc)
        extra_info = {"traceback": traceback.format_exc()}
        unexpected_error = True
    finally:
        save_traj(agent, output, exit_status=exit_status, result=result, extra_info=extra_info)  # type: ignore[arg-type]
    if exit_status == LimitsExceeded.__name__:
        raise typer.Exit(code=3)
    if unexpected_error:
        raise typer.Exit(code=1)
    return agent


if __name__ == "__main__":
    app()
