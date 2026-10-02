from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.docker_eval import _prepare_docker_eval_output
from featureliftbench.docker_eval import evaluate_submission_docker


def _make_python_eval_task(path: Path) -> Path:
    path.mkdir(parents=True)
    for tests in ("public_tests", "hidden_tests"):
        directory = path / tests
        directory.mkdir()
        (directory / "test_contract.py").write_text(
            "def test_placeholder():\n    assert True\n",
            encoding="utf-8",
        )
    (path / "requirements.lock").write_text("", encoding="utf-8")
    (path / "metadata.json").write_text(
        json.dumps(
            {
                "task_id": path.name,
                "language": "python",
                "source": {"name": "upstream"},
                "output": {"package": "featurelifted"},
                "environment": {
                    "allowed_dependencies": [],
                    "forbidden_dependencies": ["upstream"],
                    "forbidden_imports": ["upstream"],
                    "dependency_lock": "requirements.lock",
                },
                "tests": {
                    "command": "pytest",
                    "public": "public_tests/",
                    "hidden": "hidden_tests/",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


class _FakeDockerEvalProcess:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int | None = 0,
        hang: bool = False,
    ) -> None:
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode = returncode
        self.hang = hang
        self.killed = False

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        if self.hang and not self.killed:
            raise subprocess.TimeoutExpired(cmd=["docker"], timeout=timeout or 0)
        return self.stdout.getvalue(), self.stderr.getvalue()

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class DockerEvalTests(unittest.TestCase):
    def test_prepare_docker_eval_output_creates_writable_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "eval"
            _prepare_docker_eval_output(output_dir)

            self.assertTrue(output_dir.is_dir())
            self.assertEqual(output_dir.stat().st_mode & 0o777, 0o777)
            logs_dir = output_dir / "logs"
            self.assertTrue(logs_dir.is_dir())
            self.assertEqual(logs_dir.stat().st_mode & 0o777, 0o777)

    def test_evaluate_submission_docker_delegates_locally_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch(
                "featureliftbench.docker_eval.evaluate_submission",
                return_value={"status": "passed"},
            ) as local_eval:
                result = evaluate_submission_docker(
                    root / "task",
                    root / "submission",
                    root / "output",
                    use_docker=False,
                )

            self.assertEqual(result["status"], "passed")
            local_eval.assert_called_once()

    def test_evaluate_submission_docker_runs_container_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_python_eval_task(root / "task")
            submission_dir = root / "submission"
            output_dir = root / "output"
            for path in (submission_dir, output_dir):
                path.mkdir()
            (output_dir / "result.json").write_text(
                json.dumps({"status": "passed", "scores": {"final_score": 1.0}}),
                encoding="utf-8",
            )

            captured: dict[str, list[str]] = {}

            def _popen(command: list[str], **kwargs: object) -> _FakeDockerEvalProcess:
                captured["command"] = command
                return _FakeDockerEvalProcess()

            with mock.patch("featureliftbench.docker_eval.subprocess.Popen", side_effect=_popen):
                result = evaluate_submission_docker(
                    task_dir,
                    submission_dir,
                    output_dir,
                    image="featureliftbench-eval:latest",
                    use_docker=True,
                )

            self.assertTrue((output_dir / "logs").is_dir())
            command = captured["command"]
            self.assertEqual(command[0], "docker")
            self.assertIn("--name", command)
            self.assertIn("flb-eval-", command[command.index("--name") + 1])
            self.assertIn("featureliftbench-eval:latest", command)
            self.assertIn("--network", command)
            self.assertIn("none", command)
            self.assertIn("--memory", command)
            self.assertIn("4g", command)
            self.assertIn("--memory-swap", command)
            self.assertIn("--cpus", command)
            self.assertIn("2", command)
            self.assertIn("--pids-limit", command)
            self.assertIn("256", command)
            self.assertIn("--read-only", command)
            self.assertIn("--tmpfs", command)
            self.assertIn("/tmp:rw,nosuid,nodev,exec,size=2g", command)
            self.assertIn("--cap-drop", command)
            self.assertIn("ALL", command)
            self.assertIn("--security-opt", command)
            self.assertIn("no-new-privileges", command)
            self.assertIn("--user", command)
            self.assertIn(f"{os.getuid()}:{os.getgid()}", command)
            joined = " ".join(command)
            self.assertIn("/workspace/evaluation-capsule", joined)
            self.assertIn("/workspace/harness", joined)
            self.assertIn("/workspace/benchmark/vendor-wheels:ro", joined)
            self.assertNotIn("/workspace/tasks/", joined)
            self.assertNotIn("/workspace/benchmark/sources", joined)
            self.assertNotIn("/workspace/benchmark/references", joined)
            self.assertNotIn("reference_solution", joined)
            mount_targets = {
                command[index + 1].rsplit(":", 2)[-2]
                for index, token in enumerate(command)
                if token == "-v"
            }
            self.assertNotIn("/workspace/oracle", mount_targets)
            self.assertNotIn(
                f"/workspace/submissions/{task_dir.name}/oracle",
                mount_targets,
            )
            self.assertIn(f"{output_dir.resolve()}:/workspace/output:rw", joined)
            self.assertEqual(result["sandbox"]["backend"], "docker")
            self.assertRegex(result["evaluation_capsule_digest"], r"^[a-f0-9]{64}$")

    def test_evaluate_submission_docker_uses_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_python_eval_task(root / "task")
            submission_dir = root / "submission"
            output_dir = root / "output"
            for path in (submission_dir, output_dir):
                path.mkdir()
            (output_dir / "result.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")

            captured: dict[str, list[str]] = {}

            def _popen(command: list[str], **kwargs: object) -> _FakeDockerEvalProcess:
                captured["command"] = command
                return _FakeDockerEvalProcess()

            with mock.patch.dict(
                os.environ,
                {
                    "FEATURELIFTBENCH_DOCKER_MEMORY": "2g",
                    "FEATURELIFTBENCH_DOCKER_CPUS": "1.5",
                    "FEATURELIFTBENCH_DOCKER_PIDS": "64",
                    "FEATURELIFTBENCH_DOCKER_TMPFS": "/tmp:rw,size=512m",
                    "FEATURELIFTBENCH_COMMAND_OUTPUT_LIMIT_BYTES": "1024",
                },
            ):
                with mock.patch("featureliftbench.docker_eval.subprocess.Popen", side_effect=_popen):
                    result = evaluate_submission_docker(
                        task_dir,
                        submission_dir,
                        output_dir,
                        use_docker=True,
                    )

            command = captured["command"]
            self.assertIn("2g", command)
            self.assertIn("1.5", command)
            self.assertIn("64", command)
            self.assertIn("/tmp:rw,size=512m", command)
            self.assertIn("--env", command)
            self.assertIn("FEATURELIFTBENCH_COMMAND_OUTPUT_LIMIT_BYTES", command)
            self.assertEqual(result["sandbox"]["memory"], "2g")
            self.assertEqual(result["sandbox"]["cpus"], "1.5")

    def test_evaluate_submission_docker_auto_selects_go_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "go_task"
            submission_dir = root / "submission"
            output_dir = root / "output"
            for path in (task_dir, submission_dir, output_dir):
                path.mkdir()
            (task_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "task_id": "go_task",
                        "language": "go",
                        "source": {},
                        "feature": {},
                        "entanglement": {},
                        "output": {},
                        "environment": {},
                        "tests": {},
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "result.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")

            captured: dict[str, list[str]] = {}

            def _popen(command: list[str], **kwargs: object) -> _FakeDockerEvalProcess:
                captured["command"] = command
                return _FakeDockerEvalProcess()

            with mock.patch("featureliftbench.docker_eval.subprocess.Popen", side_effect=_popen):
                result = evaluate_submission_docker(
                    task_dir,
                    submission_dir,
                    output_dir,
                    use_docker=True,
                )

            self.assertIn("featureliftbench-eval-go:latest", captured["command"])
            self.assertEqual(result["sandbox"]["image"], "featureliftbench-eval-go:latest")

    def test_evaluate_submission_docker_writes_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_python_eval_task(root / "task")
            submission_dir = root / "submission"
            output_dir = root / "output"
            for path in (submission_dir,):
                path.mkdir()

            with mock.patch(
                "featureliftbench.docker_eval.subprocess.Popen",
                return_value=_FakeDockerEvalProcess(stderr="Killed", returncode=137),
            ):
                result = evaluate_submission_docker(
                    task_dir,
                    submission_dir,
                    output_dir,
                    use_docker=True,
                )

            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["docker_sandbox_error"])
            self.assertEqual(result["docker_returncode"], 137)
            self.assertTrue(result["resource_limited"])
            self.assertEqual(result["sandbox"]["backend"], "docker")
            self.assertTrue((output_dir / "result.json").is_file())

    def test_evaluate_submission_docker_timeout_kills_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_python_eval_task(root / "task")
            submission_dir = root / "submission"
            output_dir = root / "output"
            for path in (submission_dir,):
                path.mkdir()

            fake = _FakeDockerEvalProcess(hang=True)
            with mock.patch("featureliftbench.docker_eval.subprocess.Popen", return_value=fake):
                with mock.patch("featureliftbench.docker_eval._kill_container") as kill_mock:
                    with mock.patch.dict(
                        os.environ,
                        {"FEATURELIFTBENCH_DOCKER_EVAL_TIMEOUT_SECONDS": "30"},
                    ):
                        result = evaluate_submission_docker(
                            task_dir,
                            submission_dir,
                            output_dir,
                            use_docker=True,
                        )

            self.assertTrue(result["timed_out"])
            self.assertTrue(result["docker_sandbox_error"])
            self.assertEqual(result["docker_returncode"], 124)
            self.assertIn("timed out", result["errors"][0])
            kill_mock.assert_called_once()
            self.assertTrue(fake.killed)


if __name__ == "__main__":
    unittest.main()
