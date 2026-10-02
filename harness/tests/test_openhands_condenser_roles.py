"""SDK-free condenser role rules and AgentStore patch."""

from __future__ import annotations

import unittest
import sys
from types import SimpleNamespace
from unittest import mock

from featureliftbench.openhands_condenser.patch import apply_openhands_condenser_patch
from featureliftbench.openhands_condenser.roles import TOKEN_STUB
from featureliftbench.openhands_condenser.roles import UPDATED_STUB
from featureliftbench.openhands_condenser.roles import CondenserEvent
from featureliftbench.openhands_condenser.roles import apply_artifact_aware
from featureliftbench.openhands_condenser.roles import apply_recency_masking
from featureliftbench.openhands_condenser.roles import event_from_mapping
from featureliftbench.openhands_runner import _wrap_custom_condenser_command


def _obs(*, body: str, path: str | None = None, command: str | None = None) -> CondenserEvent:
    return CondenserEvent(
        source="environment",
        is_observation=True,
        body=body,
        path=path,
        command=command,
    )


def _write(path: str) -> CondenserEvent:
    return CondenserEvent(
        source="agent",
        is_observation=False,
        body="",
        path=path,
        command=f"cat > {path}",
        is_write=True,
        kind="FileEditorAction",
    )


class ArtifactAwareRoleTests(unittest.TestCase):
    def test_does_not_reinject_full_submission_tree(self) -> None:
        events = [
            _write("submission/featurelifted/a.py"),
            _write("submission/featurelifted/b.py"),
            _obs(body="A contents", path="submission/featurelifted/a.py"),
            _obs(body="B contents", path="submission/featurelifted/b.py"),
            _obs(body="A v2", path="submission/featurelifted/a.py"),
        ]
        out, stats = apply_artifact_aware(events)
        self.assertEqual(len(out), len(events))
        self.assertEqual(out[-1].body, "A v2")
        self.assertEqual(
            out[2].body,
            UPDATED_STUB.format(path="submission/featurelifted/a.py"),
        )
        self.assertEqual(out[3].body, "B contents")
        self.assertGreaterEqual(stats.superseded_artifact, 1)
        self.assertNotIn("A contents\nB contents", "".join(event.body for event in out))

    def test_reread_unchanged_file_keeps_stub(self) -> None:
        events = [
            _obs(body="same-body", path="repo/foo.py"),
            _obs(body="same-body", path="repo/foo.py"),
        ]
        out, stats = apply_artifact_aware(events)
        self.assertEqual(out[0].body, "same-body")
        self.assertEqual(out[1].body, "Re-read unchanged file: repo/foo.py")
        self.assertEqual(stats.re_read_stubs, 1)

    def test_hash_change_keeps_full_body(self) -> None:
        events = [
            _obs(body="v1", path="repo/foo.py"),
            _obs(body="v2", path="repo/foo.py"),
        ]
        out, stats = apply_artifact_aware(events)
        self.assertEqual(out[0].body, "v1")
        self.assertEqual(out[1].body, "v2")
        self.assertEqual(stats.re_read_stubs, 0)

    def test_reran_unchanged_command_stub(self) -> None:
        events = [
            _obs(body="ok", command="pytest -q"),
            _obs(body="ok", command="pytest -q"),
        ]
        out, _stats = apply_artifact_aware(events)
        self.assertEqual(out[1].body, "Re-ran unchanged command")

    def test_token_valve_masks_only_ephemeral(self) -> None:
        persistent = _obs(
            body="KEEP-ME-PERSISTENT-" + ("P" * 200),
            path="submission/featurelifted/pkg.py",
        )
        events = [
            _write("submission/featurelifted/pkg.py"),
            persistent,
            _obs(body="E" * 400, path="repo/tmp.py"),
            _obs(body="F" * 400, path="repo/other.py"),
        ]
        out, stats = apply_artifact_aware(events, trigger_tokens=20)
        self.assertEqual(out[1].body, persistent.body)
        self.assertTrue(any(event.body == TOKEN_STUB for event in out[2:]))
        self.assertGreater(stats.token_masked, 0)
        self.assertGreaterEqual(stats.persistent_protected, 1)

    def test_spec_path_is_persistent(self) -> None:
        events = [
            _obs(body="task text " * 50, path="TASK.md"),
            _obs(body="noise " * 80, path="repo/scratch.py"),
        ]
        out, stats = apply_artifact_aware(events, trigger_tokens=10)
        self.assertEqual(out[0].body, events[0].body)
        self.assertEqual(out[1].body, TOKEN_STUB)
        self.assertGreaterEqual(stats.persistent_protected, 1)

    def test_event_from_mapping_extracts_cat_path(self) -> None:
        event = event_from_mapping(
            {
                "source": "environment",
                "kind": "CmdOutputObservation",
                "observation": {
                    "content": "hello",
                    "command": "cat submission/featurelifted/mod.py",
                },
            }
        )
        self.assertTrue(event.is_observation)
        self.assertEqual(event.path, "submission/featurelifted/mod.py")
        self.assertEqual(event.body, "hello")


class RecencyMaskingTests(unittest.TestCase):
    def test_masks_observations_outside_window(self) -> None:
        events = [_obs(body=f"body-{index}", path=f"repo/{index}.py") for index in range(5)]
        out, stats = apply_recency_masking(events, attention_window=2)
        self.assertEqual(out[-1].body, "body-4")
        self.assertEqual(out[-2].body, "body-3")
        self.assertEqual(out[0].body, "Observation omitted (outside attention window)")
        self.assertEqual(stats.recency_masked, 3)
        self.assertEqual(len(out), 5)


class AgentStorePatchTests(unittest.TestCase):
    def test_keeps_custom_condenser_kinds(self) -> None:
        class ArtifactAwareCondenser:
            pass

        class AgentStore:
            def _maybe_build_condenser(self, agent, *, session_id=None):
                return None

        store = AgentStore()
        fake_module = SimpleNamespace(AgentStore=AgentStore)
        with mock.patch(
            "featureliftbench.openhands_condenser.patch._resolve_agent_store",
            return_value=AgentStore,
        ):
            apply_openhands_condenser_patch()
        agent = SimpleNamespace(condenser=ArtifactAwareCondenser())
        kept = AgentStore._maybe_build_condenser(store, agent, session_id="s1")
        self.assertIs(kept, agent.condenser)
        other = SimpleNamespace(condenser=object())
        self.assertIsNone(AgentStore._maybe_build_condenser(store, other, session_id="s1"))

    def test_keeps_custom_condenser_under_env_overrides(self) -> None:
        class VerificationAwareCondenser:
            pass

        custom = VerificationAwareCondenser()

        class Agent:
            def __init__(self, condenser):
                self.condenser = condenser

            def model_copy(self, update=None):
                return Agent((update or {}).get("condenser", self.condenser))

        class AgentStore:
            def _maybe_build_condenser(self, agent, *, session_id=None):
                return None

            def _apply_env_overrides(self, agent, overrides):
                return agent.model_copy(update={"condenser": None})

        with mock.patch(
            "featureliftbench.openhands_condenser.patch._resolve_agent_store",
            return_value=AgentStore,
        ):
            apply_openhands_condenser_patch()
        store = AgentStore()
        kept = AgentStore._apply_env_overrides(store, Agent(custom), overrides={})
        self.assertIs(kept.condenser, custom)


class CommandWrapTests(unittest.TestCase):
    def test_wraps_openhands_binary_for_custom_modes(self) -> None:
        env = {
            "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "artifact_aware",
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
        self.assertEqual(wrapped[3:], ["--headless", "-f", "prompt.md"])

    def test_does_not_wrap_token_mode(self) -> None:
        command = ["openhands", "--headless"]
        wrapped = _wrap_custom_condenser_command(
            command,
            {
                "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "token",
                "FEATURELIFTBENCH_CONTEXT_WINDOW_TOKENS": "131072",
                "FEATURELIFTBENCH_RESERVED_OUTPUT_TOKENS": "8192",
            },
        )
        self.assertEqual(wrapped, command)


class LaunchEntrypointTests(unittest.TestCase):
    def test_prefers_openhands_cli_entrypoint(self) -> None:
        fake_main = object()
        fake_entrypoint = SimpleNamespace(main=fake_main)
        with mock.patch.dict(
            sys.modules,
            {"openhands_cli.entrypoint": fake_entrypoint},
        ):
            from featureliftbench.openhands_condenser.launch import (
                resolve_openhands_cli_main,
            )

            self.assertIs(resolve_openhands_cli_main(), fake_main)

    def test_launch_heartbeat_writes_when_output_dir_set(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from featureliftbench.openhands_condenser.launch import _write_launch_heartbeat

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                "os.environ",
                {
                    "FEATURELIFTBENCH_AGENT_OUTPUT_DIR": tmp,
                    "FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE": "verification_aware",
                },
                clear=False,
            ):
                _write_launch_heartbeat()
            payload = json.loads((Path(tmp) / "condenser_launch.json").read_text())
            self.assertEqual(payload["event"], "launch")
            self.assertEqual(payload["mode"], "verification_aware")


if __name__ == "__main__":
    unittest.main()
