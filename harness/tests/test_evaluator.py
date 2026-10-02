from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.evaluator import CommandResult
from featureliftbench.evaluator import _base_evaluation_env
from featureliftbench.evaluator import _ensure_eval_tooling
from featureliftbench.evaluator import _install_submission
from featureliftbench.evaluator import _run_command
from featureliftbench.evaluator import _write_command_logs
from featureliftbench.evaluator import evaluate_submission


class EvaluatorTests(unittest.TestCase):
    def test_base_environment_is_deterministic(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": "/leaky/path", "PYTHONHASHSEED": "random", "TZ": "local"},
            clear=False,
        ):
            env = _base_evaluation_env()

        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(env["PYTHONHASHSEED"], "0")
        self.assertEqual(env["TZ"], "UTC")
        self.assertEqual(env["LC_ALL"], "C.UTF-8")
        self.assertEqual(env["LANG"], "C.UTF-8")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_evaluate_submission_passes_minimal_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            output_dir = root / "output"

            result = evaluate_submission(task_dir, submission_dir, output_dir)

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["build_pass"])
            self.assertTrue(result["test_pass"])
            self.assertTrue(result["original_import_pass"])
            self.assertEqual(result["scores"]["functional_gate"], 1.0)
            self.assertEqual(result["scores"]["extraction_ratio"], 0.2)
            self.assertEqual(result["environment"]["install_mode"], "path")
            self.assertTrue(result["dependency_install"]["skipped"])
            self.assertTrue(result["submission_install"]["skipped"])
            self.assertTrue((output_dir / "result.json").exists())

    def test_evaluate_submission_installs_pyproject_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (submission_dir / "pyproject.toml").write_text(
                "[build-system]\n"
                "requires = ['setuptools']\n"
                "build-backend = 'setuptools.build_meta'\n\n"
                "[project]\n"
                "name = 'featurelifted-sample'\n"
                "version = '0.0.0'\n\n"
                "[tool.setuptools]\n"
                "packages = ['featurelifted']\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_EVAL_FORCE_EDITABLE": "1"},
            ):
                result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["environment"]["install_mode"], "editable")
            self.assertIn("submission-runtime", result["environment"]["runtime_submission_dir"])
            self.assertTrue(result["submission_install"]["passed"])
            self.assertFalse(result["submission_install"]["skipped"])
            self.assertFalse(any(submission_dir.glob("*.egg-info")))

    def test_evaluate_submission_falls_back_when_pyproject_is_not_output_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (submission_dir / "pyproject.toml").write_text(
                "[build-system]\n"
                "requires = ['setuptools']\n"
                "build-backend = 'setuptools.build_meta'\n\n"
                "[project]\n"
                "name = 'not-featurelifted'\n"
                "version = '0.0.0'\n"
                "license = 'invalid-for-current-setuptools'\n",
                encoding="utf-8",
            )

            result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["environment"]["install_mode"], "path-fallback")
            self.assertTrue(result["submission_install"]["skipped"])

    def test_evaluate_submission_falls_back_when_editable_install_hides_output_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (submission_dir / "pyproject.toml").write_text(
                "[build-system]\n"
                "requires = ['setuptools']\n"
                "build-backend = 'setuptools.build_meta'\n\n"
                "[project]\n"
                "name = 'not-featurelifted'\n"
                "version = '0.0.0'\n\n"
                "[tool.setuptools]\n"
                "packages = []\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_EVAL_FORCE_EDITABLE": "1"},
            ):
                result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["environment"]["install_mode"], "path-fallback")
            self.assertTrue(result["submission_install"]["passed"])
            self.assertFalse(result["submission_install"]["skipped"])

    def test_install_submission_skips_bad_pyproject_when_direct_package_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (submission_dir / "pyproject.toml").write_text(
                "[build-system]\n"
                "requires = ['setuptools']\n"
                "build-backend = 'setuptools.backends._legacy:_Backend'\n",
                encoding="utf-8",
            )

            with mock.patch("featureliftbench.evaluator._run_command") as run_command:
                result, mode = _install_submission(
                    venv_python=root / ".venv" / "bin" / "python",
                    submission_path=submission_dir,
                    output_package="featurelifted",
                    cwd=root,
                    env={},
                    timeout_seconds=1,
                )

            run_command.assert_not_called()
            self.assertEqual(mode, "path-fallback")
            self.assertTrue(result.skipped)

    def test_evaluate_submission_fails_for_forbidden_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text(
                "import forbiddenpkg\nVALUE = 1\n",
                encoding="utf-8",
            )

            result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["original_import_pass"])
            self.assertIn(
                "featurelifted/__init__.py:1: imports forbidden module 'forbiddenpkg'",
                result["errors"],
            )

    def test_evaluate_submission_fails_for_forbidden_dependency_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (submission_dir / "pyproject.toml").write_text(
                "[build-system]\n"
                "requires = ['setuptools']\n"
                "build-backend = 'setuptools.build_meta'\n\n"
                "[project]\n"
                "name = 'featurelifted-sample'\n"
                "version = '0.0.0'\n"
                "dependencies = ['ForbiddenPkg>=1']\n\n"
                "[tool.setuptools]\n"
                "packages = ['featurelifted']\n",
                encoding="utf-8",
            )

            result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["original_import_pass"])
            self.assertIn("declares forbidden dependency 'forbiddenpkg'", result["errors"])

    def test_isolation_attack_canaries_fail_closed(self) -> None:
        payloads = {
            "workspace_tasks": "TARGET = '/workspace/tasks/sample/repo/secret.py'\nVALUE = 1\n",
            "source_archives": "TARGET = '/workspace/benchmark/sources/archives/x.tar.gz'\nVALUE = 1\n",
            "oracle_reference": "TARGET = '/workspace/submissions/sample/oracle/reference_solution'\nVALUE = 1\n",
            "absolute_glob": (
                "from pathlib import Path\n"
                "TARGET = list(Path('/workspace/benchmark/references').glob('*'))\n"
                "VALUE = 1\n"
            ),
            "subprocess": (
                "import subprocess\n"
                "subprocess.run(['/bin/true'], check=True)\n"
                "VALUE = 1\n"
            ),
            "dynamic_import": (
                "import importlib\n"
                "name = 'forbiddenpkg'\n"
                "module = importlib.import_module(name)\n"
                "VALUE = 1\n"
            ),
            "socket": (
                "import socket\n"
                "socket.socket().connect(('127.0.0.1', 9))\n"
                "VALUE = 1\n"
            ),
            "http": (
                "from urllib.request import urlopen\n"
                "urlopen('http://example.com')\n"
                "VALUE = 1\n"
            ),
        }
        for name, source in payloads.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    task_dir = _make_task(root / "sample_task")
                    submission_dir = root / "submission"
                    package = submission_dir / "featurelifted"
                    package.mkdir(parents=True)
                    (package / "__init__.py").write_text(source, encoding="utf-8")

                    result = evaluate_submission(task_dir, submission_dir, root / "output")

                    self.assertFalse(result["isolation_pass"])
                    self.assertTrue(
                        not result["isolation"]["forbidden_runtime_capabilities_pass"]
                        or not result["isolation"]["runtime_import_origin_pass"]
                    )
                    self.assertEqual(result["scores"]["functional_gate"], 0.0)

    def test_submission_symlink_fails_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            target = package / "real.py"
            target.write_text("VALUE = 1\n", encoding="utf-8")
            (package / "__init__.py").symlink_to(target.name)

            result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertFalse(result["isolation_pass"])
            self.assertFalse(result["isolation"]["forbidden_runtime_capabilities_pass"])
            self.assertTrue(
                any("symbolic links are not allowed" in error for error in result["errors"])
            )

    def test_evaluate_submission_fails_when_lock_contains_unallowed_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task", lock_text="requests==2.0\n")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")

            result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["build_pass"])
            self.assertFalse(result["dependency_install"]["passed"])
            self.assertIn(
                "dependency lock contains dependencies that are not allowed: requests",
                result["dependency_install"]["reason"] + result["dependency_install"].get("stderr", ""),
            )

    def test_ensure_eval_tooling_installs_pytest_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            venv_python = root / ".venv" / "bin" / "python"

            with mock.patch(
                "featureliftbench.evaluator._run_pytest_version_check",
                side_effect=[
                    CommandResult(
                        returncode=1,
                        duration_seconds=0.1,
                        stdout="",
                        stderr="No module named pytest",
                        reason="pytest is not available in evaluation venv",
                    ),
                    CommandResult(
                        returncode=0,
                        duration_seconds=0.1,
                        stdout="pytest 7.4.4\n",
                        stderr="",
                    ),
                ],
            ):
                with mock.patch(
                    "featureliftbench.evaluator._run_command",
                    return_value=CommandResult(
                        returncode=0,
                        duration_seconds=0.1,
                        stdout="installed pytest",
                        stderr="",
                    ),
                ):
                    tooling = _ensure_eval_tooling(
                        venv_python=venv_python,
                        cwd=root,
                        env=os.environ.copy(),
                        timeout_seconds=120,
                    )

            self.assertTrue(tooling.passed, tooling.stderr or tooling.reason)
            self.assertIn("pytest", tooling.stdout.lower())

    def test_evaluate_submission_records_eval_tooling_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            submission_dir = root / "submission"
            package = submission_dir / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")

            with mock.patch(
                "featureliftbench.evaluator._prepare_eval_venv",
                return_value=(None, None, None, ["eval tooling failed: pytest is not available in evaluation venv"]),
            ):
                result = evaluate_submission(task_dir, submission_dir, root / "output")

            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["build_pass"])
            self.assertIn("eval tooling failed", result["errors"][0])

    def test_write_command_logs_accepts_bytes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs_path = Path(tmp)
            result = CommandResult(
                returncode=0,
                duration_seconds=1.0,
                stdout=b"binary stdout",
                stderr=b"binary stderr",
            )

            _write_command_logs(logs_path, "test", result)

            self.assertEqual((logs_path / "test.stdout").read_text(encoding="utf-8"), "binary stdout")
            self.assertEqual((logs_path / "test.stderr").read_text(encoding="utf-8"), "binary stderr")

    def test_run_command_decodes_timeout_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("featureliftbench.evaluator.run_captured_command") as run_cmd:
                from featureliftbench.resource_limits import CapturedCommandResult

                run_cmd.return_value = CapturedCommandResult(
                    returncode=124,
                    duration_seconds=1.0,
                    stdout="partial out",
                    stderr="partial err",
                    timed_out=True,
                )
                result = _run_command(
                    ["echo"],
                    cwd=Path(tmp),
                    env={},
                    timeout_seconds=1,
                )

            self.assertTrue(result.timed_out)
            self.assertEqual(result.stdout, "partial out")
            self.assertEqual(result.stderr, "partial err")


def _make_task(task_dir: Path, lock_text: str = "") -> Path:
    (task_dir / "repo").mkdir(parents=True)
    (task_dir / "repo" / "sample.py").write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
    (task_dir / "public_tests").mkdir()
    (task_dir / "hidden_tests").mkdir()
    (task_dir / "evaluation").mkdir()
    (task_dir / "requirements.lock").write_text(lock_text, encoding="utf-8")
    (task_dir / "evaluation" / "forbidden_imports.txt").write_text(
        "forbiddenpkg\n",
        encoding="utf-8",
    )
    (task_dir / "evaluation" / "oracle_manifest.json").write_text("{}", encoding="utf-8")
    (task_dir / "metadata.json").write_text(
        json.dumps(_metadata(task_dir.name)),
        encoding="utf-8",
    )
    (task_dir / "public_tests" / "test_public.py").write_text(
        "import featurelifted\n\n"
        "def test_value():\n"
        "    assert featurelifted.VALUE == 1\n",
        encoding="utf-8",
    )
    (task_dir / "hidden_tests" / "test_hidden.py").write_text(
        "from featurelifted import VALUE\n\n"
        "def test_hidden_value():\n"
        "    assert VALUE == 1\n",
        encoding="utf-8",
    )
    return task_dir


def _metadata(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "language": "python",
        "source": {
            "name": "sample",
            "url": "https://example.com/sample",
            "commit": "abc123",
            "license": "MIT",
        },
        "feature": {
            "name": "sample feature",
            "description": "A sample feature.",
            "source_entrypoints": ["sample.VALUE"],
            "included_behaviors": ["export value"],
            "excluded_behaviors": [],
        },
        "entanglement": {
            "level": "low",
            "types": ["implicit_dependency_coupling"],
            "description": "Sample task with a small import boundary.",
            "signals": ["single source entrypoint", "no framework runtime"],
        },
        "output": {
            "package": "featurelifted",
            "import": "import featurelifted",
            "callable": "featurelifted.VALUE",
            "signature": "VALUE",
        },
        "environment": {
            "python": "3.11",
            "network": False,
            "timeout_seconds": 30,
            "dependency_lock": "requirements.lock",
            "allowed_dependencies": [],
            "forbidden_dependencies": ["forbiddenpkg"],
            "forbidden_imports": ["forbiddenpkg"],
        },
        "tests": {
            "public": "public_tests/",
            "hidden": "hidden_tests/",
            "command": "pytest",
        },
        "scoring_reference": {
            "copy_all_bytes": 100,
            "copy_all_loc": 10,
            "oracle_bytes": 50,
            "oracle_loc": 5,
            "oracle_dependency_count": 0,
        },
    }


if __name__ == "__main__":
    unittest.main()
