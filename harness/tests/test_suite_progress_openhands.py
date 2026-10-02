from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.openhands_usage import parse_openhands_progress_snapshot
from featureliftbench.suite_progress import SuiteBatchProgressManager
from featureliftbench.suite_progress_pollers import MiniProgressPoller
from featureliftbench.suite_progress_pollers import OpenHandsProgressPoller
from featureliftbench.suite_progress_pollers import resolve_progress_poller


class OpenHandsProgressSnapshotTests(unittest.TestCase):
    def test_parse_openhands_progress_snapshot_counts_json_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "openhands_stdout.log"
            log_path.write_text(
                "\n".join(
                    [
                        "OpenHands CLI terminal UI may not work correctly",
                        json.dumps(
                            {
                                "source": "user",
                                "llm_message": {"role": "user", "content": "hello"},
                            }
                        ),
                        json.dumps(
                            {
                                "source": "environment",
                                "tool_name": "file_editor",
                                "observation": {"is_error": False},
                            }
                        ),
                        json.dumps(
                            {
                                "source": "agent",
                                "action": {"command": "pytest public_tests/"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            snapshot = parse_openhands_progress_snapshot(log_path)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(snapshot.event_count, 3)
            self.assertEqual(snapshot.status, "Event 3 · pytest")
            self.assertIsNone(snapshot.total_tokens)

    def test_parse_openhands_progress_snapshot_aggregates_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "openhands_stdout.log"
            log_path.write_text(
                json.dumps(
                    {
                        "source": "agent",
                        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            snapshot = parse_openhands_progress_snapshot(log_path)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(snapshot.total_tokens, 120)


class ProgressPollerDispatchTests(unittest.TestCase):
    def test_resolve_progress_poller_openhands(self) -> None:
        poller = resolve_progress_poller("openhands-agent")
        self.assertIsInstance(poller, OpenHandsProgressPoller)

    def test_resolve_progress_poller_mini(self) -> None:
        poller = resolve_progress_poller("mini-swe-agent")
        self.assertIsInstance(poller, MiniProgressPoller)

    def test_openhands_poller_reads_openhands_stdout_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp)
            (agent_dir / "stdout.log").write_text(
                "mini-swe-agent (step 1, 100 tokens):\n",
                encoding="utf-8",
            )
            (agent_dir / "openhands_stdout.log").write_text(
                json.dumps({"source": "environment", "tool_name": "bash"}) + "\n",
                encoding="utf-8",
            )

            snapshot = OpenHandsProgressPoller().poll(agent_dir)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(snapshot.status, "Event 1 · bash")
            self.assertEqual(snapshot.metric_kind, "events")

    def test_mini_poller_reads_stdout_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp)
            (agent_dir / "stdout.log").write_text(
                "mini-swe-agent (step 2, 500 tokens):\n",
                encoding="utf-8",
            )
            (agent_dir / "openhands_stdout.log").write_text(
                json.dumps({"source": "environment", "tool_name": "bash"}) + "\n",
                encoding="utf-8",
            )

            snapshot = MiniProgressPoller().poll(agent_dir)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertIn("Step 2", snapshot.status)
            self.assertEqual(snapshot.metric_kind, "steps")


class OpenHandsProgressManagerTests(unittest.TestCase):
    def test_manager_uses_events_for_openhands(self) -> None:
        manager = SuiteBatchProgressManager(num_tasks=2, agent="openhands-agent")
        manager.on_task_start("task_a")
        manager.update_task_status("task_a", "Event 4 · file_editor", metric_value=4, metric_kind="events")

        self.assertEqual(manager._main_metric_text(), "4 events")

    def test_poll_task_logs_uses_openhands_poller(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task_a" / "agent"
            task_dir.mkdir(parents=True)
            (task_dir / "openhands_stdout.log").write_text(
                json.dumps({"source": "environment", "tool_name": "file_editor"}) + "\n",
                encoding="utf-8",
            )

            manager = SuiteBatchProgressManager(num_tasks=1, agent="openhands-agent")
            manager.on_task_start("task_a")
            with mock.patch.object(manager, "_poller") as poller:
                poller.poll.return_value = None
                manager.poll_task_logs(root)
                poller.poll.assert_called_once_with(task_dir)


if __name__ == "__main__":
    unittest.main()
