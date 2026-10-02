from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench import featurelift_agent
from featureliftbench import openhands_runner
from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_adapters import AgentAdapter
from featureliftbench.agent_adapters import AgentCommandResult
from featureliftbench.agent_adapters import AgentRunContext
from featureliftbench.agent_adapters import FeatureLiftAgentAdapter
from featureliftbench.agent_adapters import MiniSweAgentAdapter
from featureliftbench.agent_adapters import OpenHandsAgentAdapter
from featureliftbench.ablation import AblationOptions
from featureliftbench.agent_runner import _collect_agent_usage
from featureliftbench.agent_runner import _is_rate_limit_failure
from featureliftbench.agent_runner import _merge_suite_runs
from featureliftbench.agent_runner import _progress
from featureliftbench.agent_runner import _run_suite_task_with_retries
from featureliftbench.agent_runner import _sum_agent_usage
from featureliftbench.agent_runner import _transient_retry_reason
from featureliftbench.agent_runner import build_task_prompt
from featureliftbench.agent_runner import discover_task_dirs
from featureliftbench.agent_runner import load_skipped_runs
from featureliftbench.agent_runner import prepare_agent_workspace
from featureliftbench.agent_runner import run_agent_on_path
from featureliftbench.agent_runner import run_agent_on_task
from featureliftbench.evaluator import evaluate_submission
from featureliftbench.metadata import load_metadata
from featureliftbench.repo_graph.policy import MODE_ENV as REPO_GRAPH_MODE_ENV
from featureliftbench.repo_graph.policy import ROOT_ENV as REPO_GRAPH_ROOT_ENV
from featureliftbench.repo_graph.runtime import append_repo_graph_prompt
from featureliftbench.repo_graph.runtime import initialize_repo_graph


class AgentRunnerTests(unittest.TestCase):
    def test_adapter_stops_after_completion_artifact_is_detected(self) -> None:
        class SleepingWriterAdapter(AgentAdapter):
            def build_command(self, context, config):
                del config
                marker = context.agent_output_dir / "done.json"
                script = (
                    "from pathlib import Path; import time; "
                    f"Path({str(marker)!r}).write_text('done'); time.sleep(30)"
                )
                return [sys.executable, "-c", script]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            output = root / "agent"
            workspace.mkdir()
            output.mkdir()
            marker = output / "done.json"
            context = AgentRunContext(
                workspace_dir=workspace,
                task_file=workspace / "TASK.md",
                submission_dir=workspace / "submission",
                agent_output_dir=output,
                task_text="write marker",
            )

            result = SleepingWriterAdapter().run(
                context,
                AgentRunConfig(timeout_seconds=10),
                completion_check=lambda: marker.read_text() == "done"
                if marker.is_file()
                else False,
            )

            self.assertTrue(result.passed)
            self.assertTrue(result.completion_detected)
            self.assertFalse(result.timed_out)
            self.assertLess(result.duration_seconds, 5)

    def test_progress_broken_pipe_does_not_fail_task(self) -> None:
        with mock.patch("builtins.print", side_effect=BrokenPipeError):
            _progress(True, "detached progress")

    def test_build_task_prompt_includes_workflow_and_forbidden_gate(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "sanity"
            / "iniconfig__parse_config__001"
        )
        metadata = load_metadata(task_dir).data
        prompt = build_task_prompt(metadata)

        self.assertIn("## How to work", prompt)
        self.assertIn("smallest **behavior-complete** implementation closure", prompt)
        self.assertIn("## Closure Discipline", prompt)
        self.assertIn("not a toy rewrite for public tests", prompt)
        self.assertIn("Forbidden imports are a hard gate", prompt)
        self.assertIn("Benchmark evaluator tests are not mounted", prompt)
        self.assertIn("write your own tests", prompt)
        self.assertIn("submission/featurelifted", prompt)
        self.assertIn("Do **not** put your package in `featurelifted/` at the workspace root", prompt)
        self.assertIn("Functional Pass@1 is the primary gate", prompt)
        self.assertIn("reported independently", prompt)
        self.assertNotIn("pytest public_tests/", prompt)

    def test_build_task_prompt_go_uses_go_test_and_submission_module(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "go"
            / "tasks"
            / "humanize__bytes_format_core__001"
        )
        metadata = load_metadata(task_dir).data
        prompt = build_task_prompt(metadata)

        self.assertNotIn("go test ./public_tests/", prompt)
        self.assertIn("submission/go.mod", prompt)
        self.assertNotIn("submission/featurelifted/", prompt)
        self.assertNotIn("pytest public_tests/", prompt)

    def test_discover_task_dirs_can_filter_by_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_a")
            _make_task(dataset / "sample_b")

            filtered = discover_task_dirs(dataset, task_ids=["sample_b"])

            self.assertEqual([path.name for path in filtered], ["sample_b"])

    def test_load_skipped_runs_reads_passed_suite_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite_dir = root / "prev_run"
            (suite_dir / "sample_a").mkdir(parents=True)
            (suite_dir / "sample_b").mkdir(parents=True)
            (suite_dir / "sample_a" / "run.json").write_text(
                json.dumps({"task_id": "sample_a", "status": "passed"}),
                encoding="utf-8",
            )
            (suite_dir / "sample_b" / "run.json").write_text(
                json.dumps({"task_id": "sample_b", "status": "failed"}),
                encoding="utf-8",
            )
            (suite_dir / "suite.json").write_text(
                json.dumps(
                    {
                        "runs": [
                            {"task_id": "sample_a", "status": "passed"},
                            {"task_id": "sample_b", "status": "failed"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            skipped = load_skipped_runs(suite_dir)

            self.assertEqual(list(skipped), ["sample_a"])
            self.assertEqual(skipped["sample_a"]["status"], "passed")

    def test_merge_suite_runs_preserves_dataset_order(self) -> None:
        task_dirs = [Path("tasks/sample_a"), Path("tasks/sample_b")]
        fresh_runs = [{"task_id": "sample_b", "status": "passed"}]
        skipped_runs = {"sample_a": {"task_id": "sample_a", "status": "passed"}}

        merged = _merge_suite_runs(task_dirs, fresh_runs, skipped_runs)

        self.assertEqual([run["task_id"] for run in merged], ["sample_a", "sample_b"])

    def test_rate_limit_failure_detects_429_message(self) -> None:
        result = {
            "status": "failed",
            "agent": {"reason": "HTTP 429 Too Many Requests"},
            "errors": [],
        }

        self.assertTrue(_is_rate_limit_failure(result))

    def test_rate_limit_failure_detects_exit_status(self) -> None:
        result = {
            "status": "missing_submission",
            "agent": {"usage": {"exit_status": "RateLimitError"}, "stderr_log": ""},
            "errors": ["agent did not create any files under workspace/submission"],
        }

        self.assertTrue(_is_rate_limit_failure(result))

    def test_transient_retry_reason_detects_encrypted_empty_submission(self) -> None:
        result = {
            "status": "missing_submission",
            "submission": {"exists": False},
            "agent": {
                "usage": {
                    "exit_status": "invalid_encrypted_content",
                    "infrastructure_error": {
                        "failure_class": "invalid_encrypted_content",
                        "retryable": True,
                    },
                }
            },
            "errors": ["agent did not create any files under workspace/submission"],
        }

        self.assertEqual(_transient_retry_reason(result), "invalid_encrypted_content")

    def test_transient_retry_reason_skips_model_failure_with_package(self) -> None:
        result = {
            "status": "failed",
            "submission": {"exists": True},
            "agent": {
                "usage": {
                    "infrastructure_error": {
                        "failure_class": "tool_validation_error",
                        "retryable": True,
                    }
                }
            },
        }

        self.assertIsNone(_transient_retry_reason(result))

    def test_suite_task_retries_encrypted_empty_then_keeps_recovered_run(self) -> None:
        task_dir = Path("/tmp/fake-task")
        run_output = Path("/tmp/fake-output")
        first = {
            "task_id": "sample_task",
            "status": "missing_submission",
            "submission": {"exists": False},
            "agent": {
                "usage": {
                    "infrastructure_error": {
                        "failure_class": "invalid_encrypted_content",
                        "retryable": True,
                    }
                }
            },
            "errors": ["agent did not create any files under workspace/submission"],
        }
        second = {
            "task_id": "sample_task",
            "status": "failed",
            "submission": {"exists": True},
            "agent": {"usage": {"available": True}},
            "run_json": str(run_output / "run.json"),
        }
        config = AgentRunConfig(agent="command", command="echo", timeout_seconds=120)

        with (
            mock.patch(
                "featureliftbench.agent_runner.run_agent_on_task",
                side_effect=[first, second],
            ) as run_task,
            mock.patch("featureliftbench.agent_runner.time.sleep") as sleep,
            mock.patch(
                "featureliftbench.agent_runner._preserve_transient_attempt_agent"
            ),
            mock.patch(
                "featureliftbench.agent_runner._record_transient_retries",
                side_effect=lambda result, run_output, attempts, reasons: {
                    **result,
                    "transient_retries": {
                        "attempts": attempts,
                        "reasons": reasons,
                        "recovered": True,
                    },
                },
            ),
        ):
            result = _run_suite_task_with_retries(
                task_dir=task_dir,
                run_output=run_output,
                config=config,
                agent_config_summary=None,
                retry_rate_limit=1,
                retry_transient_api=3,
            )

        self.assertEqual(run_task.call_count, 2)
        sleep.assert_called_once()
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["submission"]["exists"])
        self.assertEqual(
            result["transient_retries"]["reasons"],
            ["invalid_encrypted_content"],
        )

    def test_prepare_agent_workspace_redacts_hidden_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            upstream_test = task_dir / "repo" / "tests" / "test_upstream.py"
            upstream_test.parent.mkdir(parents=True)
            upstream_test.write_text("def test_upstream():\\n    assert True\\n", encoding="utf-8")
            metadata = load_metadata(task_dir).data
            workspace_dir = root / "output" / "workspace"

            task_file = prepare_agent_workspace(task_dir, workspace_dir, metadata)

            self.assertTrue((workspace_dir / "repo" / "sample.py").exists())
            self.assertTrue((workspace_dir / "repo" / "tests" / "test_upstream.py").exists())
            self.assertFalse((workspace_dir / "public_tests").exists())
            self.assertTrue((workspace_dir / "submission").is_dir())
            self.assertFalse((workspace_dir / "hidden_tests").exists())
            self.assertFalse((workspace_dir / "evaluation").exists())

            redacted = json.loads((workspace_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertNotIn("scoring_reference", redacted)
            self.assertNotIn("tests", redacted)
            self.assertNotIn("entanglement", redacted)
            self.assertNotIn("difficulty", redacted)
            self.assertNotIn("source_entrypoints", redacted["feature"])
            task_text = task_file.read_text(encoding="utf-8")
            self.assertIn("## Entanglement Context", task_text)
            self.assertIn("Benchmark evaluator tests", task_text)
            self.assertIn("COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT", task_text)
            self.assertNotIn("sample.VALUE", task_text)

    def test_command_agent_run_creates_submission_and_evaluates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)

            result = run_agent_on_task(
                task_dir,
                root / "output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["agent"]["passed"])
            self.assertTrue(result["submission"]["exists"])
            self.assertFalse(result["submission"]["recovered"])
            self.assertEqual(result["evaluation"]["status"], "passed")
            self.assertEqual(result["evaluation"]["scores"]["functional_gate"], 1.0)
            self.assertEqual(result["evaluation"]["scores"]["extraction_ratio"], 0.2)
            self.assertEqual(result["agent"]["usage"]["assistant_steps"], 3)
            self.assertEqual(result["agent"]["usage"]["total_tokens"], 125)
            self.assertNotIn("cost_usd", result["agent"]["usage"])
            self.assertTrue((root / "output" / "run.json").exists())
            run_json = json.loads((root / "output" / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_json["agent"]["usage"]["prompt_tokens"], 100)
            self.assertFalse((root / "output" / "workspace" / "hidden_tests").exists())
            self.assertFalse((root / "output" / "agent" / "repo_graph_policy.json").exists())
            self.assertNotIn(
                "Repository Semantic Graph",
                (root / "output" / "agent" / "prompt.txt").read_text(encoding="utf-8"),
            )

    def test_repo_graph_bootstrap_is_identical_for_all_agent_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            prompts: list[str] = []
            roots: list[str] = []

            def fake_run(context, config, **_kwargs):
                prompts.append(context.task_text.split("## Repository Semantic Graph (RSG)", 1)[1])
                roots.append((config.env or {})[REPO_GRAPH_ROOT_ENV])
                package = context.submission_dir / "featurelifted"
                package.mkdir(parents=True, exist_ok=True)
                (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
                return AgentCommandResult(
                    name=config.agent,
                    command=[config.agent],
                    report_command=[config.agent],
                    returncode=0,
                    duration_seconds=0.01,
                    stdout="",
                    stderr="",
                )

            fake_adapter = mock.MagicMock()
            fake_adapter.run.side_effect = fake_run
            with mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter",
                return_value=fake_adapter,
            ):
                for agent in ("mini-swe-agent", "openhands-agent", "featurelift-agent"):
                    result = run_agent_on_task(
                        task_dir,
                        root / f"output-{agent}",
                        AgentRunConfig(
                            agent=agent,
                            env={REPO_GRAPH_MODE_ENV: "closure"},
                            timeout_seconds=120,
                        ),
                    )
                    self.assertEqual(result["status"], "passed")
                    self.assertFalse(result["repo_graph"]["protocol_violation"])

            self.assertEqual(len(prompts), 3)
            self.assertEqual(prompts[0], prompts[1])
            self.assertEqual(prompts[1], prompts[2])
            self.assertEqual(len(set(roots)), 3)
            self.assertTrue(all(path.endswith("/agent/state/repo_graph") for path in roots))

    def test_repo_graph_fail_fast_stops_before_agent_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            adapter = mock.MagicMock()
            with mock.patch(
                "featureliftbench.agent_runner.initialize_repo_graph",
                side_effect=ValueError("synthetic graph failure"),
            ), mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter",
                return_value=adapter,
            ):
                result = run_agent_on_task(
                    task_dir,
                    root / "output",
                    AgentRunConfig(
                        agent="mini-swe-agent",
                        env={REPO_GRAPH_MODE_ENV: "static"},
                    ),
                )

            adapter.run.assert_not_called()
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("before agent start" in error for error in result["errors"]))
            build = json.loads(
                (root / "output" / "agent" / "repo_graph_build.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(build["model_invoked"])

    def test_featurelift_agent_receives_and_can_query_enabled_repo_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace = root / "workspace"
            task_file = prepare_agent_workspace(
                task_dir,
                workspace,
                load_metadata(task_dir).data,
            )
            agent_output = root / "agent"
            state = initialize_repo_graph(
                workspace_dir=workspace,
                agent_output_dir=agent_output,
                config_env={REPO_GRAPH_MODE_ENV: "static"},
            )
            assert state is not None
            append_repo_graph_prompt(task_file, state)
            config = featurelift_agent.FeatureLiftAgentConfig(
                workspace=workspace,
                task_file=task_file,
                submission_dir=workspace / "submission",
                agent_output_dir=agent_output,
                model="openai/example",
                context_window_tokens=131072,
                reserved_output_tokens=8192,
                runtime="scaffold",
                enable_llm=False,
                api_base="",
                api_key="",
                request_timeout_seconds=30,
                max_tokens=1024,
            )
            featurelift_agent._write_state_files(
                config,
                agent_output / "state",
                task_file.read_text(encoding="utf-8"),
            )
            _system, user_prompt = featurelift_agent._build_phase_prompt(
                agent_output / "state",
                "closure_plan",
            )
            self.assertIn("repo_graph/bootstrap.md", user_prompt)
            self.assertIn("repo_graph_query", user_prompt)
            self.assertNotIn("source_entrypoints", user_prompt)
            self.assertFalse(
                (agent_output / "state" / "source_entrypoints.json").exists()
            )
            task_overlay = json.loads(
                (
                    agent_output
                    / "state"
                    / "repo_graph"
                    / "task_overlay.json"
                ).read_text(encoding="utf-8")
            )
            self.assertNotIn("source_entrypoints", task_overlay)
            self.assertNotIn("entrypoint_mapping", task_overlay)
            observation = featurelift_agent._execute_action(
                config,
                "closure_plan",
                1,
                {
                    "type": "repo_graph_query",
                    "command": "search",
                    "query": "VALUE",
                    "reason": "locate output provider",
                },
            )
            self.assertEqual(observation["status"], "success")
            self.assertIn('"name":"VALUE"', observation["output"])
            repeated = featurelift_agent._execute_action(
                config,
                "closure_plan",
                2,
                {
                    "type": "repo_graph_query",
                    "command": "search",
                    "query": "VALUE",
                    "reason": "repeat without state change",
                },
            )
            self.assertEqual(repeated["repeat_count_same_revision"], 2)
            self.assertEqual(repeated["action_priority"], "deprioritized")
            self.assertEqual(
                len((agent_output / "repo_graph_queries.jsonl").read_text().splitlines()),
                2,
            )

    def test_featurelift_evidence_mode_syncs_mutations_and_enforces_fresh_final_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace = root / "workspace"
            task_file = prepare_agent_workspace(
                task_dir,
                workspace,
                load_metadata(task_dir).data,
            )
            agent_output = root / "agent"
            state = initialize_repo_graph(
                workspace_dir=workspace,
                agent_output_dir=agent_output,
                config_env={REPO_GRAPH_MODE_ENV: "evidence"},
            )
            assert state is not None
            append_repo_graph_prompt(task_file, state)
            config = featurelift_agent.FeatureLiftAgentConfig(
                workspace=workspace,
                task_file=task_file,
                submission_dir=workspace / "submission",
                agent_output_dir=agent_output,
                model="openai/example",
                context_window_tokens=131072,
                reserved_output_tokens=8192,
                runtime="scaffold",
                enable_llm=False,
                api_base="",
                api_key="",
                request_timeout_seconds=30,
                max_tokens=1024,
                execute_actions=True,
            )
            write = featurelift_agent._execute_action(
                config,
                "extraction_plan",
                1,
                {
                    "type": "write_file",
                    "target": "featurelifted/__init__.py",
                    "content": "VALUE = 1\n",
                    "reason": "implement output API",
                },
            )
            self.assertEqual(write["status"], "success")
            self.assertEqual(
                json.loads((state.root / "submission_state.json").read_text())["revision"],
                1,
            )
            final = featurelift_agent._execute_action(
                config,
                "final_checklist",
                2,
                {
                    "type": "final_check",
                    "target": "current submission",
                    "reason": "fresh verification",
                },
            )
            self.assertEqual(final["status"], "success")
            self.assertTrue(
                json.loads((state.root / "stopping_guard.json").read_text())["ready"]
            )
            featurelift_agent._execute_action(
                config,
                "extraction_plan",
                3,
                {
                    "type": "write_file",
                    "target": "featurelifted/__init__.py",
                    "content": "VALUE = 1\nOTHER = 2\n",
                    "reason": "post-verification mutation",
                },
            )
            guard = featurelift_agent._repo_graph_native_stopping_guard(config)
            assert guard is not None
            self.assertFalse(guard["ready"])
            self.assertIn("missing_fresh_final_verification", guard["blockers"])

    def test_single_task_enables_live_progress_when_tty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)
            output_dir = root / "output"

            mock_pm = mock.MagicMock()
            mock_pm.__enter__ = mock.Mock(return_value=mock_pm)
            mock_pm.__exit__ = mock.Mock(return_value=False)

            with mock.patch("featureliftbench.agent_runner.sys.stderr.isatty", return_value=True):
                with mock.patch(
                    "featureliftbench.agent_runner.live_suite_progress",
                    return_value=mock_pm,
                ) as live_mock:
                    result = run_agent_on_task(
                        task_dir,
                        output_dir,
                        AgentRunConfig(agent="command", command=command, timeout_seconds=120),
                        progress=True,
                    )

            live_mock.assert_called_once_with(
                num_tasks=1,
                output_dir=output_dir.resolve(),
                agent="command",
                layout="flat",
            )
            mock_pm.on_task_start.assert_called_once()
            mock_pm.update_task_status.assert_called()
            mock_pm.on_task_end.assert_called_once()
            self.assertEqual(result["status"], "passed")

    def test_featurelift_agent_run_writes_protocol_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")

            result = run_agent_on_task(
                task_dir,
                root / "output",
                AgentRunConfig(
                    agent="featurelift-agent",
                    model="openai/example",
                    timeout_seconds=120,
                ),
            )

            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["agent"]["passed"])
            self.assertTrue(result["submission"]["exists"])
            self.assertEqual(result["agent"]["usage"]["agent_name"], "featurelift-agent")
            self.assertEqual(result["agent"]["usage"]["context_audit"]["context_window_tokens"], 131072)
            self.assertTrue((root / "output" / "agent" / "context_audit.jsonl").is_file())
            self.assertTrue((root / "output" / "agent" / "state" / "closure_plan.md").is_file())
            self.assertTrue((root / "output" / "agent" / "state" / "repo_map.md").is_file())
            self.assertFalse(
                (
                    root
                    / "output"
                    / "agent"
                    / "state"
                    / "source_entrypoints.json"
                ).exists()
            )
            manifest = json.loads(
                (root / "output" / "agent" / "state" / "dependency_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("source_entrypoints", manifest)
            self.assertTrue(
                (root / "output" / "workspace" / "submission" / "featurelifted" / "__init__.py").is_file()
            )

    def test_featurelift_agent_llm_closure_phase_records_provider_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace_dir = root / "workspace"
            metadata = load_metadata(task_dir).data
            task_file = prepare_agent_workspace(task_dir, workspace_dir, metadata)
            agent_output_dir = root / "agent"

            response = _FakeHttpResponse(
                {
                    "id": "chatcmpl-test",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "## Runtime Files To Inspect\n"
                                    "- repo/sample.py\n\n"
                                    "## Likely Resources\n"
                                    "- None\n\n"
                                    "## Hidden-Risk Behaviors\n"
                                    "- VALUE export\n\n"
                                    "## First Actions\n"
                                    "- Copy sample closure"
                                )
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 123,
                        "completion_tokens": 45,
                        "total_tokens": 168,
                    },
                }
            )

            with mock.patch(
                "featureliftbench.featurelift_agent.urllib.request.urlopen",
                return_value=response,
            ) as urlopen:
                code = featurelift_agent.run(
                    featurelift_agent.FeatureLiftAgentConfig(
                        workspace=workspace_dir,
                        task_file=task_file,
                        submission_dir=workspace_dir / "submission",
                        agent_output_dir=agent_output_dir,
                        model="openai/example",
                        context_window_tokens=131072,
                        reserved_output_tokens=8192,
                        runtime="scaffold",
                        enable_llm=True,
                        api_base="https://api.example.test/v1",
                        api_key="sk-test",
                        request_timeout_seconds=30,
                        max_tokens=1024,
                    )
                )

            self.assertEqual(code, 0)
            urlopen.assert_called_once()
            usage = json.loads((agent_output_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["api_calls"], 1)
            self.assertEqual(usage["prompt_tokens"], 123)
            self.assertEqual(usage["completion_tokens"], 45)
            self.assertEqual(usage["total_tokens"], 168)
            self.assertFalse(usage["context_audit"]["usage_unverified"])
            audit_lines = (agent_output_dir / "context_audit.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(audit_lines), 2)
            model_audit = json.loads(audit_lines[1])
            self.assertEqual(model_audit["phase"], "closure_plan")
            self.assertEqual(model_audit["token_source"], "provider_usage")
            self.assertEqual(model_audit["prompt_tokens"], 123)
            closure_plan = (agent_output_dir / "state" / "closure_plan.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## LLM Closure Plan", closure_plan)
            self.assertIn("Runtime Files To Inspect", closure_plan)

    def test_featurelift_agent_runs_multiple_llm_phases_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace_dir = root / "workspace"
            metadata = load_metadata(task_dir).data
            task_file = prepare_agent_workspace(task_dir, workspace_dir, metadata)
            agent_output_dir = root / "agent"

            closure_response = _FakeHttpResponse(
                {
                    "id": "chatcmpl-closure",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "```json\n"
                                    "{\n"
                                    '  "phase": "closure_plan",\n'
                                    '  "summary": "closure summary from phase one",\n'
                                    '  "actions": [{"type": "inspect_file", "target": "repo/sample.py", "reason": "source entrypoint"}],\n'
                                    '  "risks": ["constant export"]\n'
                                    "}\n"
                                    "```\n"
                                    "Inspect repo/sample.py first."
                                )
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                    },
                }
            )
            extraction_response = _FakeHttpResponse(
                {
                    "id": "chatcmpl-extraction",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "```json\n"
                                    "{\n"
                                    '  "phase": "extraction_plan",\n'
                                    '  "summary": "copy the value export",\n'
                                    '  "actions": [{"type": "write_file", "target": "submission/featurelifted/__init__.py", "reason": "export VALUE"}],\n'
                                    '  "risks": []\n'
                                    "}\n"
                                    "```\n"
                                    "Write a minimal package."
                                )
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 150,
                        "completion_tokens": 30,
                        "total_tokens": 180,
                    },
                }
            )

            with mock.patch(
                "featureliftbench.featurelift_agent.urllib.request.urlopen",
                side_effect=[closure_response, extraction_response],
            ) as urlopen:
                code = featurelift_agent.run(
                    featurelift_agent.FeatureLiftAgentConfig(
                        workspace=workspace_dir,
                        task_file=task_file,
                        submission_dir=workspace_dir / "submission",
                        agent_output_dir=agent_output_dir,
                        model="openai/example",
                        context_window_tokens=131072,
                        reserved_output_tokens=8192,
                        runtime="scaffold",
                        enable_llm=True,
                        api_base="https://api.example.test/v1",
                        api_key="sk-test",
                        request_timeout_seconds=30,
                        max_tokens=1024,
                        llm_phases=("closure_plan", "extraction_plan"),
                    )
                )

            self.assertEqual(code, 0)
            self.assertEqual(urlopen.call_count, 2)
            second_request = urlopen.call_args_list[1].args[0]
            second_payload = json.loads(second_request.data.decode("utf-8"))
            second_user_prompt = second_payload["messages"][1]["content"]
            self.assertIn("closure summary from phase one", second_user_prompt)

            usage = json.loads((agent_output_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["api_calls"], 2)
            self.assertEqual(usage["prompt_tokens"], 250)
            self.assertEqual(usage["completion_tokens"], 50)
            self.assertEqual(usage["total_tokens"], 300)
            audit_lines = (agent_output_dir / "context_audit.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(audit_lines), 3)
            self.assertEqual(json.loads(audit_lines[1])["phase"], "closure_plan")
            self.assertEqual(json.loads(audit_lines[2])["phase"], "extraction_plan")
            self.assertTrue((agent_output_dir / "state" / "closure_plan.json").is_file())
            extraction_json = json.loads(
                (agent_output_dir / "state" / "extraction_plan.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(extraction_json["phase"], "extraction_plan")

    def test_featurelift_agent_executes_bounded_phase_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace_dir = root / "workspace"
            metadata = load_metadata(task_dir).data
            task_file = prepare_agent_workspace(task_dir, workspace_dir, metadata)
            agent_output_dir = root / "agent"

            closure_response = _FakeHttpResponse(
                {
                    "id": "chatcmpl-closure-actions",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "```json\n"
                                    + json.dumps(
                                        {
                                            "phase": "closure_plan",
                                            "summary": "inspect the source file",
                                            "actions": [
                                                {
                                                    "type": "inspect_file",
                                                    "target": "repo/sample.py",
                                                    "reason": "source entrypoint",
                                                }
                                            ],
                                            "risks": [],
                                        }
                                    )
                                    + "\n```"
                                )
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                    },
                }
            )
            extraction_response = _FakeHttpResponse(
                {
                    "id": "chatcmpl-extraction-actions",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "```json\n"
                                    + json.dumps(
                                        {
                                            "phase": "extraction_plan",
                                            "summary": "write a minimal extracted package",
                                            "actions": [
                                                {
                                                    "type": "write_file",
                                                    "target": "submission/featurelifted/__init__.py",
                                                    "reason": "export required value",
                                                    "content": "VALUE = 1\n",
                                                }
                                            ],
                                            "risks": [],
                                        }
                                    )
                                    + "\n```"
                                )
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 150,
                        "completion_tokens": 30,
                        "total_tokens": 180,
                    },
                }
            )

            with mock.patch(
                "featureliftbench.featurelift_agent.urllib.request.urlopen",
                side_effect=[closure_response, extraction_response],
            ) as urlopen:
                code = featurelift_agent.run(
                    featurelift_agent.FeatureLiftAgentConfig(
                        workspace=workspace_dir,
                        task_file=task_file,
                        submission_dir=workspace_dir / "submission",
                        agent_output_dir=agent_output_dir,
                        model="openai/example",
                        context_window_tokens=131072,
                        reserved_output_tokens=8192,
                        runtime="scaffold",
                        enable_llm=True,
                        api_base="https://api.example.test/v1",
                        api_key="sk-test",
                        request_timeout_seconds=30,
                        max_tokens=1024,
                        llm_phases=("closure_plan", "extraction_plan"),
                        execute_actions=True,
                    )
                )

            self.assertEqual(code, 0)
            second_request = urlopen.call_args_list[1].args[0]
            second_payload = json.loads(second_request.data.decode("utf-8"))
            self.assertIn("VALUE = 1", second_payload["messages"][1]["content"])
            submission_init = workspace_dir / "submission" / "featurelifted" / "__init__.py"
            self.assertEqual(submission_init.read_text(encoding="utf-8"), "VALUE = 1\n")
            observations = [
                json.loads(line)
                for line in (agent_output_dir / "state" / "tool_observations.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual([item["action_type"] for item in observations], ["inspect_file", "write_file"])
            self.assertEqual([item["status"] for item in observations], ["success", "success"])
            extraction_log = (agent_output_dir / "state" / "extraction_log.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("repo/sample.py", extraction_log)
            self.assertIn("VALUE = 1", extraction_log)
            usage = json.loads((agent_output_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["exit_status"], "actions_complete")

    def test_featurelift_agent_three_phase_smoke_passes_evaluator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace_dir = root / "workspace"
            metadata = load_metadata(task_dir).data
            task_file = prepare_agent_workspace(
                task_dir,
                workspace_dir,
                metadata,
                ablation=AblationOptions(mount_public_tests=True),
            )
            agent_output_dir = root / "agent"

            closure_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-smoke-closure",
                    {
                        "phase": "closure_plan",
                        "summary": "inspect the source entrypoint before extraction",
                        "actions": [
                            {
                                "type": "inspect_file",
                                "target": "repo/sample.py",
                                "reason": "source entrypoint",
                            }
                        ],
                        "risks": ["ensure no original package import remains"],
                    },
                    prompt_tokens=100,
                    completion_tokens=20,
                )
            )
            extraction_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-smoke-extraction",
                    {
                        "phase": "extraction_plan",
                        "summary": "write the standalone feature package and run public tests",
                        "actions": [
                            {
                                "type": "write_file",
                                "target": "submission/featurelifted/__init__.py",
                                "reason": "export the required public value",
                                "content": "VALUE = 1\n",
                            },
                            {
                                "type": "run_public_tests",
                                "target": "public_tests",
                                "reason": "verify public behavior before final audit",
                            },
                        ],
                        "risks": [],
                    },
                    prompt_tokens=150,
                    completion_tokens=30,
                )
            )
            final_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-smoke-final",
                    {
                        "phase": "final_checklist",
                        "summary": "prune transient files, then run final checks",
                        "actions": [
                            {
                                "type": "prune_submission",
                                "target": "submission",
                                "reason": "remove transient cache files before final audit",
                            },
                            {
                                "type": "final_check",
                                "target": "featurelifted import and forbidden imports",
                                "reason": "final pre-submit audit",
                            }
                        ],
                        "risks": [],
                    },
                    prompt_tokens=125,
                    completion_tokens=25,
                )
            )

            with mock.patch(
                "featureliftbench.featurelift_agent.urllib.request.urlopen",
                side_effect=[closure_response, extraction_response, final_response],
            ) as urlopen:
                code = featurelift_agent.run(
                    featurelift_agent.FeatureLiftAgentConfig(
                        workspace=workspace_dir,
                        task_file=task_file,
                        submission_dir=workspace_dir / "submission",
                        agent_output_dir=agent_output_dir,
                        model="openai/example",
                        context_window_tokens=131072,
                        reserved_output_tokens=8192,
                        runtime="scaffold",
                        enable_llm=True,
                        api_base="https://api.example.test/v1",
                        api_key="sk-test",
                        request_timeout_seconds=30,
                        max_tokens=1024,
                        llm_phases=("closure_plan", "extraction_plan", "final_checklist"),
                        execute_actions=True,
                        tool_timeout_seconds=30,
                    )
                )

            self.assertEqual(code, 0)
            self.assertEqual(urlopen.call_count, 3)
            final_request = urlopen.call_args_list[2].args[0]
            final_payload = json.loads(final_request.data.decode("utf-8"))
            self.assertIn("pytest exited 0", final_payload["messages"][1]["content"])

            observations = [
                json.loads(line)
                for line in (agent_output_dir / "state" / "tool_observations.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(
                [item["action_type"] for item in observations],
                ["inspect_file", "write_file", "run_public_tests", "prune_submission", "final_check"],
            )
            self.assertEqual(observations[-1]["status"], "success")
            self.assertIn("public_tests=success", observations[-1]["summary"])
            self.assertEqual(observations[-2]["status"], "success")

            eval_result = evaluate_submission(
                task_dir,
                workspace_dir / "submission",
                root / "evaluation_result",
            )
            self.assertEqual(eval_result["status"], "passed")
            self.assertEqual(eval_result["scores"]["functional_gate"], 1.0)
            usage = json.loads((agent_output_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["api_calls"], 3)
            self.assertEqual(usage["exit_status"], "actions_complete")
            self.assertEqual(usage["tool_summary"]["total_actions"], 5)
            self.assertEqual(usage["tool_summary"]["failed_actions"], 0)
            self.assertEqual(usage["tool_summary"]["final_check_status"], "success")

    def test_featurelift_agent_repairs_failed_public_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            workspace_dir = root / "workspace"
            metadata = load_metadata(task_dir).data
            task_file = prepare_agent_workspace(
                task_dir,
                workspace_dir,
                metadata,
                ablation=AblationOptions(mount_public_tests=True),
            )
            agent_output_dir = root / "agent"

            closure_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-repair-closure",
                    {
                        "phase": "closure_plan",
                        "summary": "inspect source",
                        "actions": [
                            {
                                "type": "inspect_file",
                                "target": "repo/sample.py",
                                "reason": "source entrypoint",
                            }
                        ],
                        "risks": [],
                    },
                    prompt_tokens=100,
                    completion_tokens=20,
                )
            )
            extraction_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-repair-extraction",
                    {
                        "phase": "extraction_plan",
                        "summary": "write an initial implementation and test it",
                        "actions": [
                            {
                                "type": "write_file",
                                "target": "submission/featurelifted/__init__.py",
                                "reason": "initial implementation",
                                "content": "VALUE = 2\n",
                            },
                            {
                                "type": "run_public_tests",
                                "target": "public_tests",
                                "reason": "detect behavior mismatch",
                            },
                        ],
                        "risks": ["public tests may fail if VALUE is wrong"],
                    },
                    prompt_tokens=150,
                    completion_tokens=30,
                )
            )
            repair_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-repair-plan",
                    {
                        "phase": "repair_plan",
                        "summary": "fix the observed public-test mismatch",
                        "actions": [
                            {
                                "type": "write_file",
                                "target": "submission/featurelifted/__init__.py",
                                "reason": "public test expects VALUE == 1",
                                "content": "VALUE = 1\n",
                            },
                            {
                                "type": "run_public_tests",
                                "target": "public_tests",
                                "reason": "verify repaired behavior",
                            },
                        ],
                        "risks": [],
                    },
                    prompt_tokens=130,
                    completion_tokens=30,
                )
            )
            final_response = _FakeHttpResponse(
                _chat_payload(
                    "chatcmpl-repair-final",
                    {
                        "phase": "final_checklist",
                        "summary": "final audit after repair",
                        "actions": [
                            {
                                "type": "final_check",
                                "target": "featurelifted import and forbidden imports",
                                "reason": "final pre-submit audit",
                            }
                        ],
                        "risks": [],
                    },
                    prompt_tokens=120,
                    completion_tokens=25,
                )
            )

            with mock.patch(
                "featureliftbench.featurelift_agent.urllib.request.urlopen",
                side_effect=[closure_response, extraction_response, repair_response, final_response],
            ) as urlopen:
                code = featurelift_agent.run(
                    featurelift_agent.FeatureLiftAgentConfig(
                        workspace=workspace_dir,
                        task_file=task_file,
                        submission_dir=workspace_dir / "submission",
                        agent_output_dir=agent_output_dir,
                        model="openai/example",
                        context_window_tokens=131072,
                        reserved_output_tokens=8192,
                        runtime="scaffold",
                        enable_llm=True,
                        api_base="https://api.example.test/v1",
                        api_key="sk-test",
                        request_timeout_seconds=30,
                        max_tokens=1024,
                        llm_phases=("closure_plan", "extraction_plan", "final_checklist"),
                        execute_actions=True,
                        max_repair_rounds=1,
                        tool_timeout_seconds=30,
                    )
                )

            self.assertEqual(code, 0)
            self.assertEqual(urlopen.call_count, 4)
            repair_request = urlopen.call_args_list[2].args[0]
            repair_payload = json.loads(repair_request.data.decode("utf-8"))
            self.assertIn("failed_observations", repair_payload["messages"][1]["content"])
            self.assertIn("pytest exited 1", repair_payload["messages"][1]["content"])

            observations = [
                json.loads(line)
                for line in (agent_output_dir / "state" / "tool_observations.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(
                [item["action_type"] for item in observations],
                [
                    "inspect_file",
                    "write_file",
                    "run_public_tests",
                    "write_file",
                    "run_public_tests",
                    "final_check",
                ],
            )
            self.assertEqual(observations[2]["status"], "failed")
            self.assertEqual(observations[-1]["status"], "success")

            eval_result = evaluate_submission(
                task_dir,
                workspace_dir / "submission",
                root / "evaluation_result",
            )
            self.assertEqual(eval_result["status"], "passed")
            usage = json.loads((agent_output_dir / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(usage["api_calls"], 4)
            self.assertEqual(usage["exit_status"], "actions_complete_with_repairs")
            self.assertEqual(usage["tool_summary"]["failed_actions"], 1)
            self.assertEqual(usage["tool_summary"]["final_check_status"], "success")

    def test_featurelift_agent_tool_executor_blocks_hidden_boundary_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace_dir = root / "workspace"
            state_dir = root / "state"
            (workspace_dir / "evaluation").mkdir(parents=True)
            (workspace_dir / "evaluation" / "secret.txt").write_text("hidden\n", encoding="utf-8")
            state_dir.mkdir()
            (state_dir / "closure_plan.json").write_text(
                json.dumps(
                    {
                        "phase": "closure_plan",
                        "actions": [
                            {
                                "type": "inspect_file",
                                "target": "evaluation/secret.txt",
                                "reason": "should be blocked",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            observations = featurelift_agent._execute_phase_actions(
                featurelift_agent.FeatureLiftAgentConfig(
                    workspace=workspace_dir,
                    task_file=workspace_dir / "TASK.md",
                    submission_dir=workspace_dir / "submission",
                    agent_output_dir=root / "agent",
                    model="openai/example",
                    context_window_tokens=131072,
                    reserved_output_tokens=8192,
                    runtime="scaffold",
                    enable_llm=False,
                    api_base="",
                    api_key="",
                    request_timeout_seconds=30,
                    max_tokens=1024,
                ),
                state_dir,
                "closure_plan",
            )

            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0]["status"], "blocked")
            self.assertIn("outside the agent-visible task boundary", observations[0]["summary"])
            self.assertNotIn("hidden", json.dumps(observations[0]))

    def test_featurelift_agent_tools_accept_repo_relative_paths_and_directory_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace_dir = root / "workspace"
            state_dir = root / "state"
            (workspace_dir / "repo" / "pkg").mkdir(parents=True)
            (workspace_dir / "repo" / "pkg" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            state_dir.mkdir()
            (state_dir / "closure_plan.json").write_text(
                json.dumps(
                    {
                        "phase": "closure_plan",
                        "actions": [
                            {
                                "type": "inspect_file",
                                "target": "pkg/__init__.py",
                                "reason": "repo-relative path from repo map",
                            },
                            {
                                "type": "copy_file",
                                "source": "pkg",
                                "destination": "submission/featurelifted/pkg",
                                "target": "submission/featurelifted/pkg",
                                "reason": "copy package directory",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            observations = featurelift_agent._execute_phase_actions(
                featurelift_agent.FeatureLiftAgentConfig(
                    workspace=workspace_dir,
                    task_file=workspace_dir / "TASK.md",
                    submission_dir=workspace_dir / "submission",
                    agent_output_dir=root / "agent",
                    model="openai/example",
                    context_window_tokens=131072,
                    reserved_output_tokens=8192,
                    runtime="scaffold",
                    enable_llm=False,
                    api_base="",
                    api_key="",
                    request_timeout_seconds=30,
                    max_tokens=1024,
                ),
                state_dir,
                "closure_plan",
            )

            self.assertEqual([item["status"] for item in observations], ["success", "success"])
            self.assertEqual(observations[0]["target"], "repo/pkg/__init__.py")
            copied = workspace_dir / "submission" / "featurelifted" / "pkg" / "__init__.py"
            self.assertEqual(copied.read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_featurelift_agent_parses_llm_phases(self) -> None:
        self.assertEqual(
            featurelift_agent._parse_llm_phases("closure_plan, extraction_plan"),
            ("closure_plan", "extraction_plan"),
        )
        with self.assertRaises(ValueError):
            featurelift_agent._parse_llm_phases("")
        with self.assertRaises(ValueError):
            featurelift_agent._parse_llm_phases("closure_plan,unknown")
        with self.assertRaises(ValueError):
            featurelift_agent._parse_llm_phases("closure_plan,closure_plan")

    def test_featurelift_agent_normalizes_deepseek_api_model_name(self) -> None:
        config = featurelift_agent.FeatureLiftAgentConfig(
            workspace=Path("/tmp/workspace"),
            task_file=Path("/tmp/workspace/TASK.md"),
            submission_dir=Path("/tmp/workspace/submission"),
            agent_output_dir=Path("/tmp/agent"),
            model="deepseek/deepseek-v4-flash",
            context_window_tokens=131072,
            reserved_output_tokens=8192,
            runtime="scaffold",
            enable_llm=True,
            api_base="https://api.deepseek.com/v1",
            api_key="sk-test",
            request_timeout_seconds=30,
            max_tokens=1024,
        )

        self.assertEqual(featurelift_agent._api_model_name(config), "deepseek-v4-flash")

    def test_featurelift_agent_refuses_oversized_model_prompt_before_http(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            state_dir.mkdir()
            (state_dir / "task_brief.md").write_text("short\n", encoding="utf-8")
            (state_dir / "source_entrypoints.json").write_text("{}", encoding="utf-8")
            (state_dir / "repo_map.md").write_text("x" * 1000, encoding="utf-8")

            with mock.patch(
                "featureliftbench.featurelift_agent.urllib.request.urlopen"
            ) as urlopen:
                with self.assertRaises(featurelift_agent.ContextBudgetError) as raised:
                    featurelift_agent._run_bootstrap_llm_call(
                        featurelift_agent.FeatureLiftAgentConfig(
                            workspace=root / "workspace",
                            task_file=root / "TASK.md",
                            submission_dir=root / "submission",
                            agent_output_dir=root / "agent",
                            model="openai/example",
                            context_window_tokens=100,
                            reserved_output_tokens=10,
                            runtime="scaffold",
                            enable_llm=True,
                            api_base="https://api.example.test/v1",
                            api_key="sk-test",
                            request_timeout_seconds=30,
                            max_tokens=100,
                        ),
                        state_dir,
                    )

            urlopen.assert_not_called()
            self.assertTrue(raised.exception.audit_record["over_context"])

    def test_command_agent_can_evaluate_with_docker_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)
            eval_result = {
                "status": "passed",
                "scores": {
                    "functional_gate": 1.0,
                    "extraction_ratio": 0.5,
                    "final_score": 0.5,
                },
                "build_pass": True,
                "test_pass": True,
            }

            with mock.patch(
                "featureliftbench.agent_runner.evaluate_submission_docker",
                return_value=eval_result,
            ) as docker_eval:
                result = run_agent_on_task(
                    task_dir,
                    root / "output",
                    AgentRunConfig(agent="command", command=command, timeout_seconds=120),
                    eval_docker=True,
                    eval_docker_image="custom-eval:latest",
                )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["eval_backend"], "docker")
            self.assertEqual(result["eval_docker_image"], "custom-eval:latest")
            docker_eval.assert_called_once()
            self.assertEqual(docker_eval.call_args.kwargs["image"], "custom-eval:latest")

    def test_command_agent_can_run_with_agent_docker_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")

            def fake_docker_agent(context, config, *, image, stdout_log, stderr_log):
                package = context.submission_dir / "featurelifted"
                package.mkdir(parents=True, exist_ok=True)
                (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
                return AgentCommandResult(
                    name="command-docker",
                    command=["docker", "run"],
                    report_command=["docker", "run"],
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="created submission",
                    stderr="",
                )

            with mock.patch(
                "featureliftbench.agent_runner.run_agent_in_docker",
                side_effect=fake_docker_agent,
            ) as docker_agent:
                result = run_agent_on_task(
                    task_dir,
                    root / "output",
                    AgentRunConfig(agent="command", command="unused", timeout_seconds=120),
                    agent_docker=True,
                    agent_docker_image="featureliftbench-agent:test",
                )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["agent_backend"], "docker")
            self.assertEqual(result["agent_docker_image"], "featureliftbench-agent:test")
            docker_agent.assert_called_once()
            run_json = json.loads((root / "output" / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_json["agent_backend"], "docker")

    def test_recovers_misplaced_submission_from_workspace_featurelifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            fake_agent = root / "fake_misplaced_agent.py"
            command = _write_fake_misplaced_agent(fake_agent)

            result = run_agent_on_task(
                task_dir,
                root / "output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )

            self.assertNotEqual(result["status"], "missing_submission")
            self.assertTrue(result["submission"]["exists"])
            self.assertTrue(result["submission"]["recovered"])
            self.assertEqual(result["submission"]["recovery_sources"], ["workspace/featurelifted"])
            self.assertTrue(
                (root / "output" / "workspace" / "featurelifted" / "__init__.py").is_file()
            )
            self.assertTrue(
                (root / "output" / "workspace" / "submission" / "featurelifted" / "__init__.py").is_file()
            )

    def test_missing_submission_when_no_recoverable_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            fake_agent = root / "fake_empty_agent.py"
            command = _write_fake_empty_agent(fake_agent)

            result = run_agent_on_task(
                task_dir,
                root / "output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )

            self.assertEqual(result["status"], "missing_submission")
            self.assertFalse(result["submission"]["exists"])
            self.assertFalse(result["submission"]["recovered"])
            self.assertIn(
                "no submission files and no recoverable misplaced paths found",
                result["errors"][-1],
            )

    def test_does_not_recover_when_submission_already_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = _make_task(root / "sample_task")
            fake_agent = root / "fake_agent_with_misplaced_copy.py"
            command = _write_fake_agent_with_misplaced_copy(fake_agent)

            result = run_agent_on_task(
                task_dir,
                root / "output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["submission"]["exists"])
            self.assertFalse(result["submission"]["recovered"])

    def test_suite_json_includes_agent_usage_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_task")
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)

            result = run_agent_on_path(
                dataset,
                root / "suite_output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
            )

            self.assertEqual(result["mode"], "suite")
            self.assertEqual(result["summary"]["passed"], 1)
            self.assertEqual(result["agent_usage_totals"]["available_runs"], 1)
            self.assertEqual(result["agent_usage_totals"]["assistant_steps"], 3)
            self.assertEqual(result["agent_usage_totals"]["total_tokens"], 125)
            self.assertEqual(result["runs"][0]["agent_usage"]["total_tokens"], 125)
            suite_json = json.loads(
                (root / "suite_output" / "suite.json").read_text(encoding="utf-8")
            )
            self.assertEqual(suite_json["agent_usage_totals"]["prompt_tokens"], 100)

    def test_suite_usage_includes_contract_closure_repair_phase(self) -> None:
        runs = [
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "total_tokens": 100,
                        "api_calls": 2,
                    }
                },
                "contract_closure": {
                    "usage_totals": {
                        "available": True,
                        "total_tokens": 140,
                        "api_calls": 3,
                        "prompt_cache_hit_tokens": 70,
                        "prompt_cache_miss_tokens": 30,
                        "effective_uncached_prompt_tokens": 30,
                    }
                },
            }
        ]

        totals = _sum_agent_usage(runs)

        self.assertEqual(totals["total_tokens"], 140)
        self.assertEqual(totals["api_calls"], 3)
        self.assertEqual(totals["prompt_cache_hit_tokens"], 70)
        self.assertEqual(totals["prompt_cache_miss_tokens"], 30)

    def test_suite_can_run_tasks_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks"
            _make_task(dataset / "sample_a")
            _make_task(dataset / "sample_b")
            fake_agent = root / "fake_agent.py"
            command = _write_fake_usage_agent(fake_agent)

            result = run_agent_on_path(
                dataset,
                root / "suite_output",
                AgentRunConfig(agent="command", command=command, timeout_seconds=120),
                num_workers=2,
            )

            self.assertEqual(result["mode"], "suite")
            self.assertEqual(result["num_workers"], 2)
            self.assertEqual(result["summary"]["passed"], 2)
            self.assertEqual(result["agent_usage_totals"]["available_runs"], 2)
            self.assertEqual(result["agent_usage_totals"]["total_tokens"], 250)
            self.assertEqual([run["task_id"] for run in result["runs"]], ["sample_a", "sample_b"])
            suite_json = json.loads(
                (root / "suite_output" / "suite.json").read_text(encoding="utf-8")
            )
            self.assertEqual(suite_json["num_workers"], 2)
            self.assertEqual(suite_json["agent_usage_totals"]["assistant_steps"], 6)

    def test_collects_mini_trajectory_usage_without_cost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_output = root / "agent"
            agent_output.mkdir()
            (agent_output / "trajectory.json").write_text(
                json.dumps(
                    {
                        "messages": [
                            {"role": "system"},
                            {"role": "assistant"},
                            {"role": "user"},
                            {"role": "assistant"},
                        ],
                        "info": {
                            "exit_status": "Submitted",
                            "model_stats": {
                                "api_calls": 2,
                                "prompt_tokens": 1000,
                                "completion_tokens": 200,
                                "total_tokens": 1200,
                                "trace_tokens": 1200,
                                "billed_tokens": 1200,
                                "cost_usd": 5.0,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            usage = _collect_agent_usage("mini-swe-agent", agent_output)

            self.assertTrue(usage["available"])
            self.assertEqual(usage["assistant_steps"], 2)
            self.assertEqual(usage["total_messages"], 4)
            self.assertEqual(usage["api_calls"], 2)
            self.assertEqual(usage["total_tokens"], 1200)
            self.assertEqual(usage["exit_status"], "Submitted")
            self.assertNotIn("cost_usd", usage)

    def test_collects_mini_trajectory_usage_from_message_responses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_output = root / "agent"
            agent_output.mkdir()
            (agent_output / "trajectory.json").write_text(
                json.dumps(
                    {
                        "messages": [
                            {"role": "system"},
                            {
                                "role": "assistant",
                                "extra": {
                                    "response": {
                                        "usage": {
                                            "prompt_tokens": 100,
                                            "completion_tokens": 20,
                                            "total_tokens": 120,
                                        }
                                    }
                                },
                            },
                            {"role": "user"},
                            {
                                "role": "assistant",
                                "extra": {
                                    "response": {
                                        "usage": {
                                            "prompt_tokens": 150,
                                            "completion_tokens": 30,
                                        }
                                    }
                                },
                            },
                        ],
                        "info": {
                            "exit_status": "Submitted",
                            "model_stats": {"api_calls": 2},
                        },
                    }
                ),
                encoding="utf-8",
            )

            usage = _collect_agent_usage("mini-swe-agent", agent_output)

            self.assertTrue(usage["available"])
            self.assertEqual(usage["api_calls"], 2)
            self.assertEqual(usage["prompt_tokens"], 250)
            self.assertEqual(usage["completion_tokens"], 50)
            self.assertEqual(usage["total_tokens"], 300)

    def test_missing_agent_usage_is_non_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usage = _collect_agent_usage("command", Path(tmp) / "agent")

            self.assertFalse(usage["available"])
            self.assertIn("not found", usage["reason"])

    def test_sums_agent_usage_for_suite(self) -> None:
        runs = [
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "assistant_steps": 2,
                        "api_calls": 2,
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    }
                }
            },
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "assistant_steps": 3,
                        "api_calls": 3,
                        "prompt_tokens": 20,
                        "completion_tokens": 7,
                        "total_tokens": 27,
                    }
                }
            },
            {"agent": {"usage": {"available": False, "reason": "missing"}}},
        ]

        totals = _sum_agent_usage(runs)

        self.assertEqual(totals["available_runs"], 2)
        self.assertEqual(totals["missing_runs"], 1)
        self.assertEqual(totals["assistant_steps"], 5)
        self.assertEqual(totals["api_calls"], 5)
        self.assertEqual(totals["prompt_tokens"], 30)
        self.assertEqual(totals["completion_tokens"], 12)
        self.assertEqual(totals["total_tokens"], 42)

    def test_collects_usage_json_v1_context_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_output = root / "agent"
            agent_output.mkdir()
            (agent_output / "usage.json").write_text(
                json.dumps(
                    {
                        "schema_version": "featureliftbench.agent_usage.v1",
                        "agent_name": "featurelift-agent",
                        "model": "openai/example",
                        "assistant_steps": 0,
                        "api_calls": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "context_audit": {
                            "available": True,
                            "context_window_tokens": 131072,
                            "reserved_output_tokens": 8192,
                            "max_prompt_tokens_per_call": 4000,
                            "max_total_tokens_per_call": 4000,
                            "context_violation": False,
                            "usage_unverified": True,
                            "history_policy": "stateful_bounded",
                        },
                        "tool_summary": {
                            "available": True,
                            "actions_enabled": True,
                            "total_actions": 3,
                            "success_actions": 2,
                            "failed_actions": 1,
                            "blocked_actions": 0,
                            "timeout_actions": 0,
                            "error_actions": 0,
                            "final_check_status": "failed",
                            "public_tests_status": "success",
                            "action_types": {"write_file": 1, "run_public_tests": 1, "final_check": 1},
                        },
                    }
                ),
                encoding="utf-8",
            )

            usage = _collect_agent_usage("featurelift-agent", agent_output)

            self.assertTrue(usage["available"])
            self.assertEqual(usage["schema_version"], "featureliftbench.agent_usage.v1")
            self.assertEqual(usage["agent_name"], "featurelift-agent")
            self.assertEqual(usage["model"], "openai/example")
            self.assertEqual(usage["context_audit"]["context_window_tokens"], 131072)
            self.assertTrue(usage["context_audit"]["usage_unverified"])
            self.assertEqual(usage["tool_summary"]["total_actions"], 3)
            self.assertEqual(usage["tool_summary"]["failed_actions"], 1)
            self.assertEqual(usage["tool_summary"]["action_types"]["final_check"], 1)

    def test_sums_context_audit_for_suite(self) -> None:
        runs = [
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "total_tokens": 0,
                        "context_audit": {
                            "available": True,
                            "max_prompt_tokens_per_call": 100,
                            "max_total_tokens_per_call": 120,
                            "context_violation": False,
                            "usage_unverified": True,
                            "compression_mode": "token",
                            "condensation_events": 2,
                            "forgotten_event_count": 30,
                        },
                    }
                }
            },
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "total_tokens": 0,
                        "context_audit": {
                            "available": True,
                            "max_prompt_tokens_per_call": 200,
                            "max_total_tokens_per_call": 240,
                            "context_violation": True,
                            "usage_unverified": False,
                            "compression_mode": "token",
                            "condensation_events": 1,
                            "forgotten_event_count": 12,
                        },
                    }
                }
            },
        ]

        totals = _sum_agent_usage(runs)

        audit = totals["context_audit"]
        self.assertEqual(audit["available_runs"], 2)
        self.assertEqual(audit["context_violation_runs"], 1)
        self.assertEqual(audit["usage_unverified_runs"], 1)
        self.assertEqual(audit["max_prompt_tokens_per_call"], 200)
        self.assertEqual(audit["token_compression_runs"], 2)
        self.assertEqual(audit["condensation_events"], 3)
        self.assertEqual(audit["forgotten_event_count"], 42)

    def test_sums_tool_summary_for_suite(self) -> None:
        runs = [
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "tool_summary": {
                            "available": True,
                            "actions_enabled": True,
                            "total_actions": 3,
                            "success_actions": 3,
                            "failed_actions": 0,
                            "blocked_actions": 0,
                            "timeout_actions": 0,
                            "error_actions": 0,
                            "final_check_status": "success",
                        },
                    }
                }
            },
            {
                "agent": {
                    "usage": {
                        "available": True,
                        "tool_summary": {
                            "available": True,
                            "actions_enabled": True,
                            "total_actions": 2,
                            "success_actions": 1,
                            "failed_actions": 1,
                            "blocked_actions": 0,
                            "timeout_actions": 0,
                            "error_actions": 0,
                            "final_check_status": "failed",
                        },
                    }
                }
            },
        ]

        totals = _sum_agent_usage(runs)

        tool_summary = totals["tool_summary"]
        self.assertEqual(tool_summary["available_runs"], 2)
        self.assertEqual(tool_summary["actions_enabled_runs"], 2)
        self.assertEqual(tool_summary["runs_with_failed_actions"], 1)
        self.assertEqual(tool_summary["final_check_failed_runs"], 1)
        self.assertEqual(tool_summary["total_actions"], 5)
        self.assertEqual(tool_summary["failed_actions"], 1)

    def test_mini_adapter_builds_expected_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = AgentRunContext(
                workspace_dir=root / "workspace",
                task_file=root / "workspace" / "TASK.md",
                submission_dir=root / "workspace" / "submission",
                agent_output_dir=root / "agent",
                task_text="Solve this task",
            )
            adapter = MiniSweAgentAdapter()
            config = AgentRunConfig(
                agent="mini-swe-agent",
                agent_bin="mini",
                model="openai/example",
                config="mini.yaml",
                yolo=True,
                step_limit=24,
                extra_args=("--final-prompt", "write the record now"),
            )

            command = adapter.build_command(context, config)
            report_command = adapter.build_report_command(context, config)

            self.assertEqual(command[:3], [sys.executable, "-m", "featureliftbench.mini_live_runner"])
            self.assertIn("--task", command)
            self.assertIn("Solve this task", command)
            self.assertIn("--output", command)
            self.assertIn(str(root / "agent" / "trajectory.json"), command)
            self.assertIn("--exit-immediately", command)
            self.assertIn("--model", command)
            self.assertIn("openai/example", command)
            self.assertIn("--config", command)
            self.assertIn("mini.yaml", command)
            self.assertIn("--yolo", command)
            self.assertIn("--step-limit", command)
            self.assertIn("24", command)
            self.assertIn("--final-prompt", command)
            self.assertIn("write the record now", command)
            self.assertIn("@TASK.md", report_command)
            self.assertNotIn("Solve this task", report_command)

    def test_mini_adapter_uses_agent_environment_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "miniswe" / "bin"
            bin_dir.mkdir(parents=True)
            mini = bin_dir / "mini"
            python = bin_dir / "python"
            mini.write_text("#!/bin/sh\n", encoding="utf-8")
            python.write_text("#!/bin/sh\n", encoding="utf-8")
            mini.chmod(0o755)
            python.chmod(0o755)
            context = AgentRunContext(
                workspace_dir=root / "workspace",
                task_file=root / "workspace" / "TASK.md",
                submission_dir=root / "workspace" / "submission",
                agent_output_dir=root / "agent",
                task_text="Audit this task",
            )
            config = AgentRunConfig(
                agent="mini-swe-agent",
                agent_bin=str(mini),
                model="openai/example",
            )

            command = MiniSweAgentAdapter().build_command(context, config)

            self.assertEqual(command[0], str(python))
            self.assertEqual(
                command[1:3], ["-m", "featureliftbench.mini_live_runner"]
            )

    def test_featurelift_agent_adapter_builds_expected_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = AgentRunContext(
                workspace_dir=root / "workspace",
                task_file=root / "workspace" / "TASK.md",
                submission_dir=root / "workspace" / "submission",
                agent_output_dir=root / "agent",
                task_text="Solve this task",
            )
            adapter = FeatureLiftAgentAdapter()
            config = AgentRunConfig(
                agent="featurelift-agent",
                model="openai/example",
                extra_args=("--context-window", "128000"),
            )

            command = adapter.build_command(context, config)

            self.assertEqual(command[:3], [sys.executable, "-m", "featureliftbench.featurelift_agent"])
            self.assertIn("run", command)
            self.assertIn("--workspace", command)
            self.assertIn(str(root / "workspace"), command)
            self.assertIn("--submission-dir", command)
            self.assertIn(str(root / "workspace" / "submission"), command)
            self.assertIn("--agent-output-dir", command)
            self.assertIn(str(root / "agent"), command)
            self.assertIn("--model", command)
            self.assertIn("openai/example", command)
            self.assertIn("--context-window", command)
            self.assertIn("128000", command)

    def test_openhands_agent_adapter_builds_expected_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = AgentRunContext(
                workspace_dir=root / "workspace",
                task_file=root / "workspace" / "TASK.md",
                submission_dir=root / "workspace" / "submission",
                agent_output_dir=root / "agent",
                task_text="Solve this task",
            )
            adapter = OpenHandsAgentAdapter()
            config = AgentRunConfig(
                agent="openhands-agent",
                model="deepseek/deepseek-v4-flash",
                command="openhands run --prompt-file {prompt_file}",
                timeout_seconds=120,
                extra_args=("--extra", "value"),
            )

            command = adapter.build_command(context, config)

            self.assertEqual(command[:3], [sys.executable, "-m", "featureliftbench.openhands_runner"])
            self.assertIn("run", command)
            self.assertIn("--workspace", command)
            self.assertIn(str(root / "workspace"), command)
            self.assertIn("--submission-dir", command)
            self.assertIn(str(root / "workspace" / "submission"), command)
            self.assertIn("--agent-output-dir", command)
            self.assertIn(str(root / "agent"), command)
            self.assertIn("--timeout-seconds", command)
            self.assertIn("110", command)
            self.assertIn("--model", command)
            self.assertIn("deepseek/deepseek-v4-flash", command)
            self.assertIn("--openhands-command", command)
            self.assertIn("openhands run --prompt-file {prompt_file}", command)
            self.assertIn("--extra", command)
            self.assertIn("value", command)

    def test_openhands_token_mode_generates_isolated_settings_for_native_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_settings = root / "home" / ".openhands" / "agent_settings.json"
            global_settings.parent.mkdir(parents=True)
            global_settings.write_text('{"global": true}', encoding="utf-8")

            def fake_generate(args, *, env, **kwargs):
                self.assertEqual(args[1], "-c")
                settings_path = Path(env["FLB_AGENT_SETTINGS_OUT"])
                metadata_path = Path(env["FLB_AGENT_SETTINGS_META_OUT"])
                self.assertNotEqual(settings_path, global_settings)
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                settings_path.write_text(
                    json.dumps(
                        {
                            "llm": {"max_input_tokens": 57344},
                            "condenser": {
                                "max_tokens": 57344,
                                "max_size": 1000000,
                                "keep_first": 4,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                metadata_path.write_text(
                    json.dumps(
                        {
                            "openhands_version": "test",
                            "openhands_sdk_version": "test-sdk",
                            "settings": {
                                "agent_max_input_tokens": 57344,
                                "condenser_max_tokens": 57344,
                                "condenser_max_size": 1000000,
                                "condenser_keep_first": 4,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="", stderr="")

            for native in ("true", "false"):
                output = root / f"agent-{native}"
                output.mkdir()
                env = {
                    "HOME": str(root / "home"),
                    "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "token",
                    "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "65536",
                    "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "8192",
                    "FEATURELIFTBENCH_OPENHANDS_CONDENSER_KEEP_FIRST": "4",
                    "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MAX_EVENTS": "1000000",
                    "LLM_NATIVE_TOOL_CALLING": native,
                }
                with (
                    mock.patch.object(
                        openhands_runner,
                        "_resolve_openhands_python",
                        return_value="/fake/python",
                    ),
                    mock.patch.object(
                        openhands_runner.subprocess,
                        "run",
                        side_effect=fake_generate,
                    ),
                ):
                    openhands_runner._maybe_seed_agent_settings(
                        ["openhands"], env, output
                    )

                expected = output / "openhands_persistence" / "agent_settings.json"
                self.assertEqual(env["OPENHANDS_PERSISTENCE_DIR"], str(expected.parent))
                self.assertTrue(expected.is_file())
                policy = json.loads((output / "context_policy.json").read_text())
                self.assertEqual(policy["status"], "configured")
                self.assertEqual(policy["trigger_tokens"], 57344)
                self.assertEqual(policy["settings"]["condenser_max_size"], 1000000)
                self.assertEqual(global_settings.read_text(), '{"global": true}')

    def test_openhands_token_mode_fails_fast_when_settings_cannot_be_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "agent"
            output.mkdir()
            env = {
                "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "token",
                "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "65536",
                "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "8192",
            }
            with mock.patch.object(
                openhands_runner,
                "_resolve_openhands_python",
                return_value=None,
            ):
                with self.assertRaisesRegex(RuntimeError, "could not resolve"):
                    openhands_runner._maybe_seed_agent_settings(
                        ["openhands"], env, output
                    )

    def test_openhands_runner_missing_command_writes_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")

            code = openhands_runner.run(
                openhands_runner.OpenHandsRunnerConfig(
                    workspace_dir=workspace,
                    task_file=task_file,
                    submission_dir=workspace / "submission",
                    agent_output_dir=agent_output,
                    model="deepseek/deepseek-v4-flash",
                    openhands_command="",
                )
            )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            command_record = json.loads(
                (agent_output / "openhands_command.json").read_text(encoding="utf-8")
            )

            self.assertEqual(code, 2)
            self.assertEqual(usage["agent_name"], "openhands-agent")
            self.assertEqual(usage["exit_status"], "not_configured")
            self.assertFalse(usage["context_audit"]["available"])
            self.assertTrue(usage["context_audit"]["usage_unverified"])
            self.assertFalse(command_record["configured"])
            self.assertTrue((agent_output / "openhands_task.md").is_file())

    def test_openhands_runner_appends_registered_experiment_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            appendix = root / "condition.md"
            appendix.write_text("Condition: static closure hint.\n", encoding="utf-8")
            config = openhands_runner.OpenHandsRunnerConfig(
                workspace_dir=workspace,
                task_file=task_file,
                submission_dir=workspace / "submission",
                agent_output_dir=root / "agent",
            )

            with mock.patch.dict(
                os.environ,
                {openhands_runner.PROMPT_APPEND_FILE_ENV: str(appendix)},
                clear=False,
            ):
                prompt = openhands_runner._build_openhands_prompt(config)

            self.assertIn("Registered Experimental Condition", prompt)
            self.assertIn("Condition: static closure hint.", prompt)
            self.assertIn("does not grant access to hidden tests", prompt)

    def test_openhands_runner_executes_command_template_and_merges_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "from pathlib import Path\n"
                "import json\n"
                "import sys\n"
                "submission = Path(sys.argv[1])\n"
                "agent = Path(sys.argv[2])\n"
                "prompt = Path(sys.argv[3])\n"
                "pkg = submission / 'featurelifted'\n"
                "pkg.mkdir(parents=True, exist_ok=True)\n"
                "(pkg / '__init__.py').write_text('VALUE = 1\\n', encoding='utf-8')\n"
                "(agent / 'prompt_seen.txt').write_text(prompt.read_text(encoding='utf-8'), encoding='utf-8')\n"
                "(agent / 'openhands_usage.json').write_text(json.dumps({\n"
                "    'assistant_steps': 3,\n"
                "    'api_calls': 2,\n"
                "    'prompt_tokens': 100,\n"
                "    'completion_tokens': 25,\n"
                "    'context_audit': {\n"
                "        'available': True,\n"
                "        'runtime': 'openhands',\n"
                "        'history_policy': 'external_openhands',\n"
                "        'max_prompt_tokens_per_call': 80,\n"
                "        'max_total_tokens_per_call': 105,\n"
                "        'usage_unverified': False,\n"
                "    },\n"
                "}), encoding='utf-8')\n",
                encoding="utf-8",
            )
            command_template = (
                "{python} "
                f"{shlex.quote(str(fake_openhands))} "
                "{submission_dir} {agent_output_dir} {prompt_file}"
            )

            code = openhands_runner.run(
                openhands_runner.OpenHandsRunnerConfig(
                    workspace_dir=workspace,
                    task_file=task_file,
                    submission_dir=workspace / "submission",
                    agent_output_dir=agent_output,
                    model="deepseek/deepseek-v4-flash",
                    openhands_command=command_template,
                    timeout_seconds=30,
                )
            )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            prompt_seen = (agent_output / "prompt_seen.txt").read_text(encoding="utf-8")

            self.assertEqual(code, 0)
            self.assertEqual(usage["agent_name"], "openhands-agent")
            self.assertEqual(usage["exit_status"], "passed")
            self.assertEqual(usage["assistant_steps"], 3)
            self.assertEqual(usage["api_calls"], 2)
            self.assertEqual(usage["prompt_tokens"], 100)
            self.assertEqual(usage["completion_tokens"], 25)
            self.assertEqual(usage["total_tokens"], 125)
            self.assertEqual(usage["context_audit"]["max_prompt_tokens_per_call"], 80)
            self.assertFalse(usage["context_audit"]["usage_unverified"])
            self.assertIn("FeatureLiftBench Task for OpenHands", prompt_seen)
            self.assertTrue((workspace / "submission" / "featurelifted" / "__init__.py").is_file())

    def test_openhands_runner_splits_json_events_from_stdout_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "import json\n"
                "print('OpenHands banner')\n"
                "print(json.dumps({'source': 'environment', 'tool_name': 'bash'}))\n"
                "print('plain status line')\n",
                encoding="utf-8",
            )
            command_template = "{python} " + shlex.quote(str(fake_openhands))

            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY": "0"},
                clear=False,
            ):
                code = openhands_runner.run(
                    openhands_runner.OpenHandsRunnerConfig(
                        workspace_dir=workspace,
                        task_file=task_file,
                        submission_dir=workspace / "submission",
                        agent_output_dir=agent_output,
                        model="deepseek/deepseek-v4-flash",
                        openhands_command=command_template,
                        timeout_seconds=30,
                    )
                )

            stdout_text = (agent_output / "openhands_stdout.log").read_text(encoding="utf-8")
            events_text = (agent_output / "openhands_events.jsonl").read_text(encoding="utf-8")
            self.assertEqual(code, 0)
            self.assertIn("OpenHands banner", stdout_text)
            self.assertIn("plain status line", stdout_text)
            self.assertNotIn('"tool_name": "bash"', stdout_text)
            self.assertIn('"tool_name": "bash"', events_text)

    def test_openhands_runner_turns_zero_exit_tool_validation_error_into_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "import json\n"
                "print(json.dumps({\n"
                "    'id': 'event-1',\n"
                "    'kind': 'AgentErrorEvent',\n"
                "    'tool_name': 'terminal',\n"
                "    'error': \"Error validating tool 'terminal': Failed to provide security_risk field\",\n"
                "}))\n",
                encoding="utf-8",
            )
            command_template = "{python} " + shlex.quote(str(fake_openhands))

            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY": "0"},
                clear=False,
            ):
                code = openhands_runner.run(
                    openhands_runner.OpenHandsRunnerConfig(
                        workspace_dir=workspace,
                        task_file=task_file,
                        submission_dir=workspace / "submission",
                        agent_output_dir=agent_output,
                        model="deepseek/deepseek-v4-flash",
                        openhands_command=command_template,
                        timeout_seconds=30,
                    )
                )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            failure = json.loads(
                (agent_output / "openhands_infrastructure_error.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                code, openhands_runner.OPENHANDS_TOOL_VALIDATION_ERROR_RETURN_CODE
            )
            self.assertEqual(usage["exit_status"], "tool_validation_error")
            self.assertEqual(
                usage["infrastructure_error"]["failure_class"],
                "tool_validation_error",
            )
            self.assertTrue(failure["retryable"])
            self.assertTrue(failure["promoted_to_process_failure"])

    def test_openhands_runner_records_invalid_encrypted_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "import json\n"
                "print(json.dumps({\n"
                "    'id': 'event-enc',\n"
                "    'kind': 'ConversationErrorEvent',\n"
                "    'code': 'LLMBadRequestError',\n"
                "    'detail': 'The encrypted content for item *** could not be verified. "
                "Reason: Encrypted content could not be decrypted or parsed.',\n"
                "}))\n",
                encoding="utf-8",
            )
            command_template = "{python} " + shlex.quote(str(fake_openhands))

            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY": "0"},
                clear=False,
            ):
                code = openhands_runner.run(
                    openhands_runner.OpenHandsRunnerConfig(
                        workspace_dir=workspace,
                        task_file=task_file,
                        submission_dir=workspace / "submission",
                        agent_output_dir=agent_output,
                        model="openai/gpt-5.6-luna",
                        openhands_command=command_template,
                        timeout_seconds=30,
                    )
                )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            failure = json.loads(
                (agent_output / "openhands_infrastructure_error.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(code, openhands_runner.OPENHANDS_INFRASTRUCTURE_ERROR_RETURN_CODE)
            self.assertEqual(usage["exit_status"], "invalid_encrypted_content")
            self.assertEqual(failure["failure_class"], "invalid_encrypted_content")
            self.assertTrue(failure["retryable"])
            self.assertTrue(failure["promoted_to_process_failure"])

    def test_openhands_runner_keeps_zero_exit_when_tool_validation_recovers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            submission = workspace / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text("", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "import json\n"
                "print(json.dumps({\n"
                "    'id': 'event-1',\n"
                "    'kind': 'AgentErrorEvent',\n"
                "    'tool_name': 'terminal',\n"
                "    'error': \"Error validating tool 'terminal': Failed to provide security_risk field\",\n"
                "}))\n",
                encoding="utf-8",
            )
            command_template = "{python} " + shlex.quote(str(fake_openhands))

            with mock.patch.dict(
                os.environ,
                {"FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY": "0"},
                clear=False,
            ):
                code = openhands_runner.run(
                    openhands_runner.OpenHandsRunnerConfig(
                        workspace_dir=workspace,
                        task_file=task_file,
                        submission_dir=workspace / "submission",
                        agent_output_dir=agent_output,
                        model="deepseek/deepseek-v4-flash",
                        openhands_command=command_template,
                        timeout_seconds=30,
                    )
                )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            failure = json.loads(
                (agent_output / "openhands_infrastructure_error.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(code, 0)
            self.assertEqual(usage["exit_status"], "passed")
            self.assertEqual(
                usage["infrastructure_error"]["failure_class"],
                "tool_validation_error",
            )
            self.assertFalse(failure["promoted_to_process_failure"])
            self.assertTrue(failure["retryable"])

    def test_openhands_runner_kills_command_when_log_limit_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "import time\n"
                "for _ in range(200):\n"
                "    print('x' * 100, flush=True)\n"
                "time.sleep(10)\n",
                encoding="utf-8",
            )
            command_template = "{python} " + shlex.quote(str(fake_openhands))

            with mock.patch.dict(
                os.environ,
                {
                    "FEATURELIFTBENCH_COMMAND_OUTPUT_LIMIT_BYTES": "1024",
                    "FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY": "0",
                },
                clear=False,
            ):
                code = openhands_runner.run(
                    openhands_runner.OpenHandsRunnerConfig(
                        workspace_dir=workspace,
                        task_file=task_file,
                        submission_dir=workspace / "submission",
                        agent_output_dir=agent_output,
                        model="deepseek/deepseek-v4-flash",
                        openhands_command=command_template,
                        timeout_seconds=30,
                    )
                )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 125)
            self.assertEqual(usage["exit_status"], "log_limit_exceeded")
            self.assertLessEqual((agent_output / "openhands_stdout.log").stat().st_size, 1200)

    def test_openhands_runner_kills_command_when_step_limit_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent_output = root / "agent"
            workspace.mkdir()
            task_file = workspace / "TASK.md"
            task_file.write_text("Extract the useful behavior.\n", encoding="utf-8")
            fake_openhands = root / "fake_openhands.py"
            fake_openhands.write_text(
                "import json\n"
                "import time\n"
                "for i in range(3):\n"
                "    print(json.dumps({'type': 'assistant_message', 'message': str(i)}), flush=True)\n"
                "time.sleep(10)\n",
                encoding="utf-8",
            )
            command_template = "{python} " + shlex.quote(str(fake_openhands))

            with mock.patch.dict(
                os.environ,
                {
                    "FEATURELIFTBENCH_OPENHANDS_MAX_STEPS": "2",
                    "FEATURELIFTBENCH_OPENHANDS_USAGE_PROXY": "0",
                },
                clear=False,
            ):
                code = openhands_runner.run(
                    openhands_runner.OpenHandsRunnerConfig(
                        workspace_dir=workspace,
                        task_file=task_file,
                        submission_dir=workspace / "submission",
                        agent_output_dir=agent_output,
                        model="deepseek/deepseek-v4-flash",
                        openhands_command=command_template,
                        timeout_seconds=30,
                    )
                )

            usage = json.loads((agent_output / "usage.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 123)
            self.assertEqual(usage["exit_status"], "step_limit_exceeded")
            self.assertEqual(usage["assistant_steps"], 3)


def _make_task(task_dir: Path) -> Path:
    (task_dir / "repo").mkdir(parents=True)
    (task_dir / "repo" / "sample.py").write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
    (task_dir / "public_tests").mkdir()
    (task_dir / "hidden_tests").mkdir()
    (task_dir / "evaluation").mkdir()
    (task_dir / "requirements.lock").write_text("", encoding="utf-8")
    (task_dir / "evaluation" / "forbidden_imports.txt").write_text("sample\n", encoding="utf-8")
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


def _write_fake_usage_agent(path: Path) -> str:
    path.write_text(
        "from pathlib import Path\n"
        "import json\n"
        "import sys\n"
        "submission = Path(sys.argv[1])\n"
        "agent_output = Path(sys.argv[2])\n"
        "package = submission / 'featurelifted'\n"
        "package.mkdir(parents=True, exist_ok=True)\n"
        "(package / '__init__.py').write_text('VALUE = 1\\n', encoding='utf-8')\n"
        "(agent_output / 'usage.json').write_text(json.dumps({\n"
        "    'assistant_steps': 3,\n"
        "    'total_messages': 7,\n"
        "    'api_calls': 3,\n"
        "    'prompt_tokens': 100,\n"
        "    'completion_tokens': 25,\n"
        "    'total_tokens': 125,\n"
        "    'cost_usd': 999,\n"
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


def _write_fake_misplaced_agent(path: Path) -> str:
    path.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "submission = Path(sys.argv[1])\n"
        "workspace = submission.parent\n"
        "package = workspace / 'featurelifted'\n"
        "package.mkdir(parents=True, exist_ok=True)\n"
        "(package / '__init__.py').write_text('VALUE = 1\\n', encoding='utf-8')\n"
        "print('created misplaced submission')\n",
        encoding="utf-8",
    )
    return (
        f"{shlex.quote(sys.executable)} "
        f"{shlex.quote(str(path))} "
        "{submission_dir} "
        "{agent_output_dir}"
    )


def _write_fake_empty_agent(path: Path) -> str:
    path.write_text(
        "print('submitted without files')\n",
        encoding="utf-8",
    )
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(path))}"


def _write_fake_agent_with_misplaced_copy(path: Path) -> str:
    path.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "submission = Path(sys.argv[1])\n"
        "workspace = submission.parent\n"
        "for target in (submission / 'featurelifted', workspace / 'featurelifted'):\n"
        "    target.mkdir(parents=True, exist_ok=True)\n"
        "    (target / '__init__.py').write_text('VALUE = 1\\n', encoding='utf-8')\n"
        "print('created submission and misplaced copy')\n",
        encoding="utf-8",
    )
    return (
        f"{shlex.quote(sys.executable)} "
        f"{shlex.quote(str(path))} "
        "{submission_dir} "
        "{agent_output_dir}"
    )


class _FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _chat_payload(
    response_id: str,
    content_json: dict,
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict:
    return {
        "id": response_id,
        "choices": [
            {
                "message": {
                    "content": "```json\n" + json.dumps(content_json) + "\n```",
                }
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


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
            "forbidden_dependencies": ["sample"],
            "forbidden_imports": ["sample"],
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
