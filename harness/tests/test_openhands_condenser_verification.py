"""Verification-aware condenser: ledger, keep-full, overflow, wrap."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from featureliftbench.openhands_condenser.patch import apply_openhands_condenser_patch
from featureliftbench.openhands_condenser.roles import TOKEN_STUB
from featureliftbench.openhands_condenser.roles import CondenserEvent
from featureliftbench.openhands_condenser.roles import event_from_mapping
from featureliftbench.openhands_condenser.verification import LEDGER_HEADER
from featureliftbench.openhands_condenser.verification import RECORDED_STUB
from featureliftbench.openhands_condenser.verification import apply_verification_aware
from featureliftbench.openhands_runner import _wrap_custom_condenser_command


def _obs(
    *,
    body: str,
    command: str | None = None,
    path: str | None = None,
    exit_code: int | None = 0,
    tool_name: str = "terminal",
) -> CondenserEvent:
    return CondenserEvent(
        source="environment",
        is_observation=True,
        body=body,
        path=path,
        command=command,
        exit_code=exit_code,
        tool_name=tool_name,
        kind="TerminalObservation",
    )


def _action(command: str) -> CondenserEvent:
    return CondenserEvent(
        source="agent",
        is_observation=False,
        body="",
        command=command,
        kind="CmdRunAction",
        tool_name="terminal",
    )


class VerificationAwareTests(unittest.TestCase):
    def test_three_pytest_dumps_keep_latest_and_ledger(self) -> None:
        events = [
            _obs(
                body="===== 1 passed in 0.01s =====",
                command="pytest tests/test_a.py -q",
                exit_code=0,
            ),
            _obs(
                body="===== 2 passed in 0.02s =====",
                command="pytest tests/test_b.py -q",
                exit_code=0,
            ),
            _obs(
                body="===== 3 passed in 0.03s =====",
                command="pytest tests/test_c.py -q",
                exit_code=0,
            ),
        ]
        out, stats = apply_verification_aware(events)
        self.assertEqual(out[-1].body, events[-1].body)
        self.assertTrue(out[0].body.startswith(LEDGER_HEADER))
        self.assertIn("pytest tests/test_a.py -q", out[0].body)
        self.assertIn("pytest tests/test_b.py -q", out[0].body)
        self.assertIn("pytest tests/test_c.py -q", out[0].body)
        self.assertEqual(out[1].body, RECORDED_STUB)
        self.assertEqual(stats.self_test_n, 3)
        self.assertEqual(stats.kept_full, 1)
        self.assertEqual(stats.ledger_lines, 3)
        self.assertEqual(stats.stubbed, 1)

    def test_ledger_updates_in_place_on_rerun(self) -> None:
        events = [
            _obs(
                body="===== 1 failed in 0.01s =====\nValueError: boom",
                command="pytest tests/test_a.py -q",
                exit_code=1,
            ),
            _obs(
                body="===== 1 passed in 0.01s =====",
                command="pytest tests/test_a.py -q",
                exit_code=0,
            ),
            _obs(
                body="===== 2 passed in 0.02s =====",
                command="pytest tests/test_b.py -q",
                exit_code=0,
            ),
        ]
        out, stats = apply_verification_aware(events)
        self.assertEqual(stats.ledger_lines, 2)
        # Latest failure and latest test stay full; middle becomes ledger host.
        self.assertIn("ValueError: boom", out[0].body)
        self.assertTrue(out[1].body.startswith(LEDGER_HEADER))
        self.assertIn("1 passed", out[1].body)
        self.assertNotIn("1 failed", out[1].body)
        self.assertEqual(out[2].body, events[2].body)

    def test_keeps_last_failure_traceback(self) -> None:
        fail_body = "Traceback (most recent call last):\nValueError: bad\n===== 1 failed ====="
        events = [
            _obs(body=fail_body, command="python -c 'raise ValueError()'", exit_code=1),
            _obs(
                body="===== 1 passed in 0.01s =====",
                command="pytest tests/ok.py -q",
                exit_code=0,
            ),
        ]
        out, stats = apply_verification_aware(events)
        self.assertEqual(out[0].body, fail_body)
        self.assertEqual(out[1].body, events[1].body)
        self.assertEqual(stats.kept_full, 2)
        self.assertEqual(stats.stubbed, 0)

    def test_does_not_compress_cat_repo(self) -> None:
        events = [
            _obs(body="file contents here", command="cat repo/foo.py", path="repo/foo.py"),
            _obs(
                body="===== 1 passed =====",
                command="pytest tests/t.py -q",
                exit_code=0,
            ),
            _obs(
                body="===== 2 passed =====",
                command="pytest tests/u.py -q",
                exit_code=0,
            ),
        ]
        out, _stats = apply_verification_aware(events)
        self.assertEqual(out[0].body, "file contents here")
        self.assertTrue(out[1].body.startswith(LEDGER_HEADER))
        self.assertEqual(out[2].body, events[2].body)

    def test_overflow_does_not_mask_code_evidence(self) -> None:
        fail_body = "AssertionError: nope\n" + ("X" * 400)
        cat_repo = "E" * 800
        cat_submission = "class Impl:\n    pass\n" + ("Z" * 400)
        grep_hit = "foo.py:12: def target():\n" + ("G" * 200)
        events = [
            _obs(body="TASK TEXT " * 40, path="TASK.md", command=None, exit_code=None),
            _obs(
                body=fail_body,
                command="python -c 'assert False'",
                exit_code=1,
            ),
            _obs(
                body="noise " * 200,
                command="pytest tests/old.py -q",
                exit_code=0,
            ),
            _obs(
                body="===== 1 passed =====",
                command="pytest tests/new.py -q",
                exit_code=0,
            ),
            _obs(body=cat_repo, path="repo/scratch.py", command="cat repo/scratch.py"),
            _obs(
                body=cat_submission,
                path="submission/featurelifted/mod.py",
                command="cat submission/featurelifted/mod.py",
            ),
            _obs(
                body=grep_hit,
                path="repo/foo.py",
                command="grep -n def repo/foo.py",
            ),
        ]
        out, stats = apply_verification_aware(events, trigger_tokens=20)
        self.assertEqual(out[0].body, events[0].body)
        self.assertEqual(out[1].body, fail_body)
        self.assertTrue(out[2].body.startswith(LEDGER_HEADER))
        self.assertEqual(out[3].body, events[3].body)
        self.assertEqual(out[4].body, cat_repo)
        self.assertEqual(out[5].body, cat_submission)
        self.assertEqual(out[6].body, grep_hit)
        self.assertEqual(stats.overflow_masked, 0)
        self.assertNotIn(TOKEN_STUB, [event.body for event in out])

    def test_overflow_does_not_mask_source_when_no_self_tests(self) -> None:
        events = [
            _obs(body="Y" * 150, command="cat repo/a.py", path="repo/a.py"),
        ]
        out, stats = apply_verification_aware(events, trigger_tokens=100)
        self.assertEqual(out[0].body, events[0].body)
        self.assertEqual(stats.overflow_masked, 0)
        self.assertEqual(stats.self_test_n, 0)

    def test_pairs_command_from_preceding_action(self) -> None:
        events = [
            _action("pytest tests/a.py -q"),
            CondenserEvent(
                source="environment",
                is_observation=True,
                body="===== 1 passed =====",
                exit_code=0,
                tool_name="terminal",
            ),
            _action("pytest tests/b.py -q"),
            CondenserEvent(
                source="environment",
                is_observation=True,
                body="===== 2 passed =====",
                exit_code=0,
                tool_name="terminal",
            ),
            _action("pytest tests/c.py -q"),
            CondenserEvent(
                source="environment",
                is_observation=True,
                body="===== 3 passed =====",
                exit_code=0,
                tool_name="terminal",
            ),
        ]
        out, stats = apply_verification_aware(events)
        self.assertEqual(stats.self_test_n, 3)
        host = next(event for event in out if event.body.startswith(LEDGER_HEADER))
        self.assertIn("pytest tests/a.py -q", host.body)

    def test_event_from_mapping_keeps_exit_code(self) -> None:
        event = event_from_mapping(
            {
                "source": "environment",
                "tool_name": "terminal",
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "TerminalObservation",
                    "command": "pytest -q",
                    "exit_code": 1,
                    "content": [{"type": "text", "text": "failed"}],
                },
            }
        )
        self.assertEqual(event.exit_code, 1)
        self.assertEqual(event.command, "pytest -q")
        self.assertEqual(event.body, "failed")
        self.assertEqual(event.tool_name, "terminal")


class VerificationAuditTests(unittest.TestCase):
    def test_record_stats_writes_jsonl(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from featureliftbench.openhands_condenser.kinds import _record_stats
        from featureliftbench.openhands_condenser.verification import VerificationStats

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                "os.environ",
                {"FEATURELIFTBENCH_AGENT_OUTPUT_DIR": tmp},
                clear=False,
            ):
                _record_stats(
                    VerificationStats(self_test_n=2, stubbed=1),
                    extra={"mode": "verification_aware"},
                )
            path = Path(tmp) / "condenser_audit.jsonl"
            self.assertTrue(path.is_file())
            payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(payload["recorded"])
            self.assertEqual(payload["self_test_n"], 2)
            self.assertEqual(payload["mode"], "verification_aware")


class VerificationPatchWrapTests(unittest.TestCase):
    def test_keeps_verification_aware_kind(self) -> None:
        class VerificationAwareCondenser:
            pass

        class AgentStore:
            def _maybe_build_condenser(self, agent, *, session_id=None):
                return None

        store = AgentStore()
        with mock.patch(
            "featureliftbench.openhands_condenser.patch._resolve_agent_store",
            return_value=AgentStore,
        ):
            apply_openhands_condenser_patch()
        agent = SimpleNamespace(condenser=VerificationAwareCondenser())
        kept = AgentStore._maybe_build_condenser(store, agent, session_id="s1")
        self.assertIs(kept, agent.condenser)

    def test_wraps_openhands_for_verification_aware(self) -> None:
        env = {
            "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "verification_aware",
            "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "131072",
            "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "8192",
        }
        with mock.patch(
            "featureliftbench.openhands_runner._resolve_openhands_python",
            return_value="/opt/uv-tools/openhands/bin/python",
        ):
            wrapped = _wrap_custom_condenser_command(
                ["openhands", "--headless", "-f", "prompt.md"],
                env,
            )
        self.assertEqual(
            wrapped[:3],
            [
                "/opt/uv-tools/openhands/bin/python",
                "-m",
                "featureliftbench.openhands_condenser.launch",
            ],
        )


if __name__ == "__main__":
    unittest.main()
