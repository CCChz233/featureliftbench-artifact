from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from featureliftbench import cli
from featureliftbench.agent_adapters import AgentRunConfig


class CliRunAgentTests(unittest.TestCase):
    def test_run_agent_env_enables_docker_eval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "tasks"
            input_dir.mkdir()
            output_dir = root / "output"
            loaded = SimpleNamespace(
                run_config=AgentRunConfig(agent="command"),
                summary={},
            )

            with mock.patch.dict(os.environ, {"FEATURELIFTBENCH_EVAL_DOCKER": "1"}):
                with mock.patch(
                    "featureliftbench.agent_config.load_agent_run_config",
                    return_value=loaded,
                ):
                    with mock.patch(
                        "featureliftbench.agent_runner.run_agent_on_path",
                        return_value={"mode": "suite", "summary": {"failed": 0}},
                    ) as run_agent:
                        code = cli.main(
                            [
                                "run-agent",
                                str(input_dir),
                                "--output",
                                str(output_dir),
                                "--eval-docker-image",
                                "custom-eval:latest",
                            ]
                        )

            self.assertEqual(code, 0)
            self.assertTrue(run_agent.call_args.kwargs["eval_docker"])
            self.assertEqual(run_agent.call_args.kwargs["eval_docker_image"], "custom-eval:latest")

    def test_run_agent_env_enables_agent_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "tasks"
            input_dir.mkdir()
            output_dir = root / "output"
            loaded = SimpleNamespace(
                run_config=AgentRunConfig(agent="command"),
                summary={},
            )

            with mock.patch.dict(
                os.environ,
                {
                    "FEATURELIFTBENCH_AGENT_DOCKER": "1",
                    "FEATURELIFTBENCH_AGENT_DOCKER_IMAGE": "custom-agent:latest",
                },
            ):
                with mock.patch(
                    "featureliftbench.agent_config.load_agent_run_config",
                    return_value=loaded,
                ):
                    with mock.patch(
                        "featureliftbench.agent_runner.run_agent_on_path",
                        return_value={"mode": "suite", "summary": {"failed": 0}},
                    ) as run_agent:
                        code = cli.main(
                            [
                                "run-agent",
                                str(input_dir),
                                "--output",
                                str(output_dir),
                            ]
                        )

            self.assertEqual(code, 0)
            self.assertTrue(run_agent.call_args.kwargs["agent_docker"])
            self.assertEqual(run_agent.call_args.kwargs["agent_docker_image"], "custom-agent:latest")


if __name__ == "__main__":
    unittest.main()
