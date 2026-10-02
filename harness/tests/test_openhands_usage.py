from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.openhands_usage import MAX_ALLOWED_PROMPT_TOKENS
from featureliftbench.openhands_usage import openhands_context_limits
from featureliftbench.openhands_usage import openhands_context_policy
from featureliftbench.openhands_usage import parse_events_jsonl
from featureliftbench.openhands_usage import parse_openhands_compression_events
from featureliftbench.openhands_usage import write_usage_from_events


class OpenHandsUsageTests(unittest.TestCase):
    def test_token_context_policy_derives_trigger_and_target(self) -> None:
        policy = openhands_context_policy(
            {
                "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "token",
                "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "65536",
                "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "8192",
                "FEATURELIFTBENCH_OPENHANDS_CONDENSER_KEEP_FIRST": "4",
                "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MAX_EVENTS": "1000000",
            }
        )

        self.assertEqual(policy.condenser_trigger_tokens, 57344)
        self.assertEqual(policy.condenser_target_tokens, 28672)
        self.assertTrue(policy.token_compression_enabled)
        self.assertTrue(policy.requires_seeded_settings)

    def test_custom_condenser_modes_are_seeded_but_not_token_summarizer(self) -> None:
        for mode in ("recency_masking", "artifact_aware", "verification_aware"):
            policy = openhands_context_policy(
                {
                    "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": mode,
                    "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "131072",
                    "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "8192",
                }
            )
            self.assertEqual(policy.compression_mode, mode)
            self.assertTrue(policy.requires_seeded_settings)
            self.assertFalse(policy.token_compression_enabled)
            self.assertEqual(policy.condenser_trigger_tokens, 122880)
            self.assertEqual(policy.condenser_attention_window, 100)

    def test_parse_condensation_events_counts_without_retaining_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "openhands_events.jsonl"
            events_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "kind": "Condensation",
                                "forgotten_event_ids": ["e1", "e2", "e3"],
                                "summary": "private full summary text",
                            }
                        ),
                        json.dumps(
                            {
                                "kind": "Condensation",
                                "forgotten_event_ids": ["e4"],
                                "summary": "",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant_message",
                                "usage": {
                                    "prompt_tokens": 100,
                                    "completion_tokens": 10,
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            counts = parse_openhands_compression_events(events_path)
            usage = parse_events_jsonl(events_path)

        self.assertEqual(counts["condensation_events"], 2)
        self.assertEqual(counts["forgotten_event_count"], 4)
        self.assertEqual(counts["condensation_summaries_nonempty"], 1)
        self.assertEqual(usage["context_audit"]["condensation_events"], 2)
        self.assertNotIn("private full summary text", json.dumps(usage))

    def test_parse_events_jsonl_aggregates_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "openhands_events.jsonl"
            events_path.write_text(
                "\n".join(
                    [
                        "OpenHands CLI terminal UI may not work correctly",
                        json.dumps(
                            {
                                "type": "assistant_message",
                                "usage": {
                                    "prompt_tokens": 100,
                                    "completion_tokens": 20,
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant_message",
                                "message": {
                                    "usage": {
                                        "prompt_tokens": 50,
                                        "completion_tokens": 10,
                                    }
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            usage = parse_events_jsonl(events_path)

            self.assertEqual(usage["prompt_tokens"], 150)
            self.assertEqual(usage["completion_tokens"], 30)
            self.assertEqual(usage["api_calls"], 2)
            self.assertFalse(usage["context_audit"]["usage_unverified"])
            self.assertEqual(usage["context_audit"]["token_source"], "openhands_jsonl")
            self.assertEqual(usage["context_audit"]["max_prompt_tokens_per_call"], 100)

    def test_parse_events_jsonl_marks_context_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "openhands_events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "assistant_message",
                        "usage": {
                            "prompt_tokens": MAX_ALLOWED_PROMPT_TOKENS + 1,
                            "completion_tokens": 1,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            usage = parse_events_jsonl(events_path)

            self.assertTrue(usage["context_audit"]["context_violation"])

    def test_parse_events_jsonl_counts_openhands_agent_action_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "openhands_events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "source": "agent",
                        "action": {"command": "view", "path": "/flb/workspace/repo"},
                        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            usage = parse_events_jsonl(events_path)

            self.assertEqual(usage["assistant_steps"], 1)

    def test_parse_events_jsonl_without_usage_is_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "openhands_events.jsonl"
            events_path.write_text(
                json.dumps({"type": "system", "message": "hello"}) + "\n",
                encoding="utf-8",
            )

            usage = parse_events_jsonl(events_path)

            self.assertTrue(usage["context_audit"]["usage_unverified"])
            self.assertFalse(usage["context_audit"]["available"])

    def test_write_usage_from_events_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events_path = root / "openhands_events.jsonl"
            output_path = root / "openhands_usage.json"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "assistant_message",
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            written = write_usage_from_events(events_path, output_path)

            self.assertIsNotNone(written)
            self.assertTrue(output_path.is_file())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["prompt_tokens"], 10)
            self.assertFalse(payload["context_audit"]["usage_unverified"])

    def test_context_limits_can_be_configured_from_env(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "1000",
                "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "100",
            },
            clear=False,
        ):
            limits = openhands_context_limits()

        self.assertEqual(limits.context_window_tokens, 1000)
        self.assertEqual(limits.reserved_output_tokens, 100)
        self.assertEqual(limits.max_allowed_prompt_tokens, 900)

    def test_parse_events_jsonl_uses_configured_context_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_path = Path(tmp) / "openhands_events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "assistant_message",
                        "usage": {"prompt_tokens": 901, "completion_tokens": 1},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "1000",
                    "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "100",
                },
                clear=False,
            ):
                usage = parse_events_jsonl(events_path)

            self.assertEqual(usage["context_audit"]["context_window_tokens"], 1000)
            self.assertEqual(usage["context_audit"]["max_allowed_prompt_tokens"], 900)
            self.assertTrue(usage["context_audit"]["context_violation"])


if __name__ == "__main__":
    unittest.main()
