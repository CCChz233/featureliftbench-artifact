from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_runner import _archive_previous_run
from featureliftbench.agent_runner import _read_task_attempt
from featureliftbench.agent_runner import _task_at_max_attempts
from featureliftbench.agent_runner import _validate_retained_runs
from featureliftbench.agent_runner import _write_suite_checkpoint
from featureliftbench.agent_runner import _SuiteCheckpointContext
from featureliftbench.agent_runner import load_skipped_runs
from featureliftbench.agent_runner import run_agent_on_path
from featureliftbench.agent_runner import run_agent_on_suite
from featureliftbench.agent_runner import run_agent_on_task
from featureliftbench.suite_utils import load_retained_runs
from featureliftbench.suite_utils import parse_retry_only_statuses
from featureliftbench.suite_utils import rebuild_suite_summary
from featureliftbench.suite_utils import evaluation_payload
from featureliftbench.suite_utils import run_failure_class

try:
    from harness.tests import test_agent_runner
except ImportError:  # pragma: no cover - supports running from harness/tests directly.
    import test_agent_runner

_make_task = test_agent_runner._make_task
_write_fake_usage_agent = test_agent_runner._write_fake_usage_agent


class SuiteResumeTests(unittest.TestCase):
    def test_resume_rejects_incompatible_experiment_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = _make_task(Path(tmp) / "sample_task")
            retained = {
                "sample_task": {
                    "task_id": "sample_task",
                    "status": "passed",
                    "experiment_conditions": {"model": "different-model"},
                }
            }

            with self.assertRaisesRegex(
                ValueError,
                "resume would mix incompatible",
            ):
                _validate_retained_runs(
                    retained,
                    task_dirs=[task],
                    config=AgentRunConfig(agent="command", model="expected-model"),
                    agent_docker=False,
                    agent_docker_image="",
                    eval_docker=False,
                    eval_docker_image="",
                )

    def test_load_retained_runs_filters_by_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            (suite_dir / "task_a").mkdir(parents=True)
            (suite_dir / "task_b").mkdir(parents=True)
            (suite_dir / "task_a" / "run.json").write_text(
                json.dumps({"task_id": "task_a", "status": "passed"}),
                encoding="utf-8",
            )
            (suite_dir / "task_b" / "run.json").write_text(
                json.dumps({"task_id": "task_b", "status": "missing_submission"}),
                encoding="utf-8",
            )
            (suite_dir / "suite.json").write_text(
                json.dumps(
                    {
                        "runs": [
                            {"task_id": "task_a", "status": "passed"},
                            {"task_id": "task_b", "status": "missing_submission"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            passed_only = load_retained_runs(suite_dir, retain_statuses=frozenset({"passed"}))
            resume_retained = load_retained_runs(
                suite_dir,
                retain_statuses=frozenset({"passed", "failed"}),
            )

            self.assertEqual(list(passed_only), ["task_a"])
            self.assertEqual(sorted(resume_retained), ["task_a"])

    def test_load_retained_runs_falls_back_to_run_json_without_suite_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            (suite_dir / "task_a").mkdir(parents=True)
            (suite_dir / "task_b").mkdir(parents=True)
            (suite_dir / "task_a" / "run.json").write_text(
                json.dumps({"task_id": "task_a", "status": "passed"}),
                encoding="utf-8",
            )
            (suite_dir / "task_b" / "run.json").write_text(
                json.dumps({"task_id": "task_b", "status": "failed"}),
                encoding="utf-8",
            )

            resume_retained = load_retained_runs(
                suite_dir,
                retain_statuses=frozenset({"passed", "failed"}),
            )

            self.assertEqual(sorted(resume_retained), ["task_a", "task_b"])

    def test_checkpoint_mid_suite_retains_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            (suite_dir / "task_a").mkdir(parents=True)
            (suite_dir / "task_b").mkdir(parents=True)
            run_a = {
                "task_id": "task_a",
                "status": "passed",
                "attempt": 1,
                "agent": {"passed": True, "usage": {"available": False}},
                "submission": {"exists": True},
                "evaluation": {"status": "passed", "scores": {"final_score": 1.0}},
                "run_json": str(suite_dir / "task_a" / "run.json"),
            }
            (suite_dir / "task_a" / "run.json").write_text(json.dumps(run_a), encoding="utf-8")
            config = AgentRunConfig(agent="command", command="echo", timeout_seconds=120)
            ctx = _SuiteCheckpointContext(
                output_path=suite_dir,
                ordered_task_dirs=[suite_dir / "task_a", suite_dir / "task_b"],
                retained_runs={},
                config=config,
                agent_config_summary={},
                worker_count=1,
                retry_rate_limit=1,
                retry_transient_api=3,
                retry_only_statuses=frozenset({"missing_submission", "failed", "not_evaluated"}),
                extra_agent_passes=0,
                max_task_attempts=None,
                eval_docker=False,
                eval_docker_image="featureliftbench-eval:latest",
                agent_docker=False,
                agent_docker_image="featureliftbench-agent:latest",
                resume_enabled=True,
                suite_source_dir=suite_dir,
                skipped_max_attempts=frozenset(),
                runnable_count=2,
            )
            _write_suite_checkpoint(ctx, [run_a])

            suite_payload = json.loads((suite_dir / "suite.json").read_text(encoding="utf-8"))
            self.assertTrue(suite_payload.get("checkpoint"))
            self.assertEqual(suite_payload["summary"]["passed"], 1)

            retained = load_retained_runs(
                suite_dir,
                retain_statuses=frozenset({"passed", "failed"}),
            )
            self.assertEqual(list(retained), ["task_a"])
            self.assertEqual(retained["task_a"]["status"], "passed")

    def test_load_skipped_runs_still_reads_only_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp) / "suite"
            (suite_dir / "task_a").mkdir(parents=True)
            (suite_dir / "task_b").mkdir(parents=True)
            (suite_dir / "task_a" / "run.json").write_text(
                json.dumps({"task_id": "task_a", "status": "passed"}),
                encoding="utf-8",
            )
            (suite_dir / "task_b" / "run.json").write_text(
                json.dumps({"task_id": "task_b", "status": "failed"}),
                encoding="utf-8",
            )
            (suite_dir / "suite.json").write_text(
                json.dumps(
                    {
                        "runs": [
                            {"task_id": "task_a", "status": "passed"},
                            {"task_id": "task_b", "status": "failed"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            skipped = load_skipped_runs(suite_dir)

            self.assertEqual(list(skipped), ["task_a"])

    def test_parse_retry_only_statuses_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            parse_retry_only_statuses("missing_submission,unknown_status")

    def test_rebuild_suite_summary_groups_tasks_by_status(self) -> None:
        summary = rebuild_suite_summary(
            [
                {"task_id": "a", "status": "passed", "agent": {"passed": True}, "submission": {"exists": True}},
                {
                    "task_id": "b",
                    "status": "missing_submission",
                    "agent": {"passed": True},
                    "submission": {"exists": False},
                },
            ]
        )

        self.assertEqual(summary["by_status"]["passed"], 1)
        self.assertEqual(summary["by_status"]["missing_submission"], 1)
        self.assertEqual(summary["tasks_by_status"]["missing_submission"], ["b"])
        self.assertEqual(summary["recovered_submissions"], 0)

    def test_rebuild_suite_summary_counts_recovered_submissions(self) -> None:
        summary = rebuild_suite_summary(
            [
                {
                    "task_id": "a",
                    "status": "failed",
                    "agent": {"passed": True},
                    "submission": {"exists": True, "recovered": True},
                },
                {
                    "task_id": "b",
                    "status": "passed",
                    "agent": {"passed": True},
                    "submission": {"exists": True, "recovered": False},
                },
            ]
        )

        self.assertEqual(summary["recovered_submissions"], 1)

    def test_rebuild_suite_summary_counts_eval_resource_categories(self) -> None:
        summary = rebuild_suite_summary(
            [
                {
                    "task_id": "a",
                    "status": "failed",
                    "agent": {"passed": True},
                    "submission": {"exists": True},
                    "evaluation": {"resource_limited": True},
                },
                {
                    "task_id": "b",
                    "status": "failed",
                    "agent": {"passed": True},
                    "submission": {"exists": True},
                    "evaluation": {"log_limit_exceeded": True},
                },
                {
                    "task_id": "c",
                    "status": "failed",
                    "agent": {"passed": True},
                    "submission": {"exists": True},
                    "evaluation": {"docker_sandbox_error": True},
                },
            ]
        )

        self.assertEqual(summary["resource_limited_failures"], 1)
        self.assertEqual(summary["log_limit_failures"], 1)
        self.assertEqual(summary["docker_sandbox_failures"], 1)

    def test_rebuild_suite_summary_counts_failure_classes(self) -> None:
        runs = [
            {
                "task_id": "passed",
                "status": "passed",
                "agent": {"passed": True, "usage": {"available": True, "api_calls": 2}},
                "submission": {"exists": True},
                "evaluation": {"status": "passed"},
            },
            {
                "task_id": "setup",
                "status": "missing_submission",
                "agent": {"passed": False, "usage": {"available": True, "api_calls": 0}},
                "submission": {"exists": False},
            },
            {
                "task_id": "rate",
                "status": "failed",
                "agent": {
                    "passed": False,
                    "reason": "429 too many requests",
                    "usage": {"available": True, "api_calls": 1},
                },
                "submission": {"exists": False},
            },
            {
                "task_id": "missing",
                "status": "missing_submission",
                "agent": {"passed": True, "usage": {"available": True, "api_calls": 3}},
                "submission": {"exists": False},
            },
            {
                "task_id": "eval",
                "status": "failed",
                "agent": {"passed": True, "usage": {"available": True, "api_calls": 3}},
                "submission": {"exists": True},
                "evaluation": {"docker_sandbox_error": True},
            },
            {
                "task_id": "model",
                "status": "failed",
                "agent": {"passed": True, "usage": {"available": True, "api_calls": 3}},
                "submission": {"exists": True},
                "evaluation": {"status": "failed", "docker_sandbox_error": False},
            },
            {
                "task_id": "step",
                "status": "failed",
                "agent": {
                    "passed": False,
                    "usage": {"available": True, "api_calls": 3, "exit_status": "step_limit_exceeded"},
                },
                "submission": {"exists": False},
            },
        ]

        summary = rebuild_suite_summary(runs)

        self.assertEqual(summary["failure_classes"]["passed"], 1)
        self.assertEqual(summary["failure_classes"]["agent_setup_failed"], 1)
        self.assertEqual(summary["failure_classes"]["rate_limited"], 1)
        self.assertEqual(summary["failure_classes"]["missing_submission"], 1)
        self.assertEqual(summary["failure_classes"]["eval_infra_failed"], 1)
        self.assertEqual(summary["failure_classes"]["model_failed"], 1)
        self.assertEqual(summary["failure_classes"]["agent_step_limited"], 1)
        self.assertEqual(run_failure_class(runs[-1]), "agent_step_limited")

    def test_evaluation_payload_lifts_eval_sandbox_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = evaluation_payload(
                {
                    "status": "failed",
                    "scores": {},
                    "public_tests": {"resource_limited": True},
                    "hidden_tests": {"log_limit_exceeded": True},
                    "sandbox": {"backend": "docker", "docker_sandbox_error": True},
                },
                Path(tmp),
            )

        self.assertTrue(payload["resource_limited"])
        self.assertTrue(payload["log_limit_exceeded"])
        self.assertTrue(payload["docker_sandbox_error"])
        self.assertEqual(payload["sandbox_backend"], "docker")

    def test_archive_previous_run_creates_attempt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "task_a"
            output.mkdir(parents=True)
            (output / "run.json").write_text(
                json.dumps({"task_id": "task_a", "status": "failed", "attempt": 1}),
                encoding="utf-8",
            )

            next_attempt, previous = _archive_previous_run(output)

            self.assertEqual(next_attempt, 2)
            self.assertEqual(previous, str(output / "run.attempt1.json"))
            self.assertTrue((output / "run.attempt1.json").is_file())

    def test_task_at_max_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task_a"
            task_dir.mkdir()
            (task_dir / "run.json").write_text(
                json.dumps({"attempt": 2}),
                encoding="utf-8",
            )

            self.assertTrue(_task_at_max_attempts(task_dir, 2))
            self.assertFalse(_task_at_max_attempts(task_dir, 3))
            self.assertEqual(_read_task_attempt(task_dir), 2)

    def test_resume_retries_missing_submission_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_a")
            _make_task(dataset / "sample_b")
            output = root / "suite_output"
            output.mkdir(parents=True)
            (output / "sample_a").mkdir()
            (output / "sample_a" / "run.json").write_text(
                json.dumps({"task_id": "sample_a", "status": "passed", "attempt": 1}),
                encoding="utf-8",
            )
            (output / "sample_b").mkdir()
            (output / "sample_b" / "run.json").write_text(
                json.dumps(
                    {"task_id": "sample_b", "status": "missing_submission", "attempt": 1}
                ),
                encoding="utf-8",
            )
            (output / "suite.json").write_text(
                json.dumps(
                    {
                        "runs": [
                            {"task_id": "sample_a", "status": "passed"},
                            {"task_id": "sample_b", "status": "missing_submission"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)

            result = run_agent_on_suite(
                [dataset / "sample_a", dataset / "sample_b"],
                output,
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
                resume_dir=output,
                resume_mode=True,
                retry_only_statuses=frozenset({"missing_submission"}),
            )

            self.assertEqual(result["summary"]["passed"], 2)
            self.assertEqual(result["resume"]["retained"], 1)
            self.assertEqual(result["resume"]["retried"], 1)
            self.assertEqual(result["runs"][0]["task_id"], "sample_a")
            self.assertEqual(result["runs"][0]["status"], "passed")
            self.assertEqual(result["runs"][1]["status"], "passed")
            self.assertTrue((output / "sample_b" / "run.attempt1.json").is_file())
            rerun_json = json.loads((output / "sample_b" / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(rerun_json["attempt"], 2)

    def test_max_task_attempts_skips_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_a")
            output = root / "suite_output"
            (output / "sample_a").mkdir(parents=True)
            (output / "sample_a" / "run.json").write_text(
                json.dumps({"task_id": "sample_a", "status": "missing_submission", "attempt": 2}),
                encoding="utf-8",
            )
            (output / "suite.json").write_text(
                json.dumps(
                    {
                        "runs": [
                            {"task_id": "sample_a", "status": "missing_submission"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)

            result = run_agent_on_suite(
                [dataset / "sample_a"],
                output,
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
                resume_dir=output,
                resume_mode=True,
                max_task_attempts=2,
            )

            self.assertEqual(result["resume"]["retried"], 0)
            self.assertEqual(result["resume"]["skipped_max_attempts"], ["sample_a"])
            self.assertEqual(result["summary"]["missing_submissions"], 1)

    def test_extra_agent_passes_reruns_failed_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_a")
            fake_agent = root / "fail_once_agent.py"
            command = _write_fail_once_agent(fake_agent)

            result = run_agent_on_path(
                dataset,
                root / "suite_output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
                extra_agent_passes=1,
            )

            self.assertEqual(result["summary"]["passed"], 1)
            self.assertEqual(result["extra_agent_passes"], 1)
            self.assertTrue((root / "suite_output" / "suite.pass1.json").is_file())
            run_json = json.loads(
                (root / "suite_output" / "sample_a" / "run.json").read_text(encoding="utf-8")
            )
            self.assertEqual(run_json["attempt"], 2)

    def test_run_agent_on_task_records_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            output = root / "output"
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)

            first = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )
            second = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )

            self.assertEqual(first["attempt"], 1)
            self.assertEqual(second["attempt"], 2)
            self.assertIn("previous_attempt_json", second)

    def test_extra_agent_passes_uses_mocked_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_a")
            output = root / "suite_output"
            config = AgentRunConfig(agent="command", command="echo", timeout_seconds=120)

            first_run = {
                "task_id": "sample_a",
                "status": "missing_submission",
                "attempt": 1,
                "agent": {"passed": True, "usage": {"available": False}},
                "submission": {"exists": False},
                "evaluation": {"status": "not-run", "scores": {}},
            }
            second_run = {
                "task_id": "sample_a",
                "status": "passed",
                "attempt": 2,
                "agent": {"passed": True, "usage": {"available": False}},
                "submission": {"exists": True},
                "evaluation": {"status": "passed", "scores": {"final_score": 1.0}},
            }

            with mock.patch(
                "featureliftbench.agent_runner._run_suite_tasks",
                side_effect=[[first_run], [second_run]],
            ) as run_tasks:
                result = run_agent_on_suite(
                    [dataset / "sample_a"],
                    output,
                    config,
                    extra_agent_passes=1,
                )

            self.assertEqual(run_tasks.call_count, 2)
            self.assertEqual(result["summary"]["passed"], 1)
            self.assertEqual(result["summary"]["tasks_by_status"]["passed"], ["sample_a"])


def _write_fail_once_agent(path: Path) -> str:
    path.write_text(
        "from pathlib import Path\n"
        "import json\n"
        "import sys\n"
        "submission = Path(sys.argv[1])\n"
        "agent_output = Path(sys.argv[2])\n"
        "marker = submission.resolve().parent.parent / 'fail_once.marker'\n"
        "if not marker.exists():\n"
        "    marker.write_text('1', encoding='utf-8')\n"
        "    print('skipping submission on first attempt')\n"
        "    sys.exit(0)\n"
        "package = submission / 'featurelifted'\n"
        "package.mkdir(parents=True, exist_ok=True)\n"
        "(package / '__init__.py').write_text('VALUE = 1\\n', encoding='utf-8')\n"
        "(agent_output / 'usage.json').write_text(json.dumps({\n"
        "    'assistant_steps': 1,\n"
        "    'api_calls': 1,\n"
        "    'prompt_tokens': 1,\n"
        "    'completion_tokens': 1,\n"
        "    'total_tokens': 2,\n"
        "}), encoding='utf-8')\n"
        "print('created submission')\n",
        encoding="utf-8",
    )
    return (
        f"{shlex.quote(sys.executable)} "
        f"{shlex.quote(str(path))} "
        "{submission_dir} "
        "{agent_output_dir}"
    )


if __name__ == "__main__":
    unittest.main()
