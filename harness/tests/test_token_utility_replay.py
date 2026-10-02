from __future__ import annotations

import json
import unittest
from pathlib import Path

from featureliftbench.token_utility_replay import attach_disk_hash
from featureliftbench.token_utility_replay import parse_ts
from featureliftbench.token_utility_replay import replay_events
from featureliftbench.token_utility_replay import sample_unique
from featureliftbench.token_utility_replay import tree_hash
from featureliftbench.token_utility_replay import UniqueSnapshot


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class TokenUtilityReplayTests(unittest.TestCase):
    def test_naive_timestamp_is_utc(self) -> None:
        naive = parse_ts("2026-08-12T16:56:48.854985")
        zulu = parse_ts("2026-08-12T16:56:48Z")
        assert naive is not None and zulu is not None
        self.assertLess(abs(naive - zulu), 1.0)

    def test_editor_replay_matches_disk(self) -> None:
        with self._tmpdir() as root:
            repo = root / "repo"
            repo.mkdir()
            (repo / "src.py").write_text("SRC = 1\n", encoding="utf-8")
            events = root / "events.jsonl"
            _write_jsonl(
                events,
                [
                    {
                        "kind": "ActionEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-12T16:00:00",
                        "action": {"command": "create", "path": "/flb/workspace/submission/featurelifted/__init__.py"},
                    },
                    {
                        "kind": "ObservationEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-12T16:00:01",
                        "observation": {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/__init__.py",
                            "is_error": False,
                            "new_content": "VALUE = 1\n",
                        },
                    },
                    {
                        "kind": "ActionEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-12T16:00:02",
                        "action": {"command": "str_replace", "path": "/flb/workspace/submission/featurelifted/__init__.py"},
                    },
                    {
                        "kind": "ObservationEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-12T16:00:03",
                        "observation": {
                            "command": "str_replace",
                            "path": "/flb/workspace/submission/featurelifted/__init__.py",
                            "is_error": False,
                            "new_content": "VALUE = 2\n",
                        },
                    },
                ],
            )
            result = replay_events(events_path=events, repo_src=repo)
            disk = root / "disk" / "featurelifted"
            disk.mkdir(parents=True)
            (disk / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")
            attach_disk_hash(result, disk)
            self.assertTrue(result.last_matches_disk)
            self.assertEqual(len(result.unique), 2)
            self.assertEqual(result.files["__init__.py"], b"VALUE = 2\n")

    def test_failed_editor_is_ignored(self) -> None:
        with self._tmpdir() as root:
            repo = root / "repo"
            repo.mkdir()
            events = root / "events.jsonl"
            _write_jsonl(
                events,
                [
                    {
                        "kind": "ObservationEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-12T16:00:01",
                        "observation": {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/__init__.py",
                            "is_error": True,
                            "new_content": "NOPE\n",
                        },
                    },
                    {
                        "kind": "ObservationEvent",
                        "tool_name": "file_editor",
                        "timestamp": "2026-08-12T16:00:02",
                        "observation": {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/__init__.py",
                            "is_error": False,
                            "new_content": "OK\n",
                        },
                    },
                ],
            )
            result = replay_events(events_path=events, repo_src=repo)
            self.assertEqual(result.files["__init__.py"], b"OK\n")
            self.assertEqual(result.editor_writes, 1)

    def test_terminal_cp_from_repo(self) -> None:
        with self._tmpdir() as root:
            repo = root / "repo"
            repo.mkdir()
            (repo / "pkg.py").write_text("X = 3\n", encoding="utf-8")
            events = root / "events.jsonl"
            _write_jsonl(
                events,
                [
                    {
                        "kind": "ActionEvent",
                        "tool_name": "terminal",
                        "timestamp": "2026-08-12T16:00:00",
                        "action": {
                            "command": "mkdir -p /flb/workspace/submission/featurelifted && "
                            "cp /flb/workspace/repo/pkg.py /flb/workspace/submission/featurelifted/__init__.py"
                        },
                    },
                    {
                        "kind": "ObservationEvent",
                        "tool_name": "terminal",
                        "timestamp": "2026-08-12T16:00:01",
                        "observation": {"is_error": False, "content": [{"type": "text", "text": "ok"}]},
                    },
                ],
            )
            result = replay_events(events_path=events, repo_src=repo)
            self.assertEqual(result.files["__init__.py"], b"X = 3\n")
            self.assertEqual(result.terminal_runs, 1)

    def test_sample_unique_keeps_first_last_and_token_marks(self) -> None:
        rows = [
            UniqueSnapshot(0, "a", 100, 1, 1, "editor"),
            UniqueSnapshot(1, "b", 1_200_000, 1, 1, "editor"),
            UniqueSnapshot(2, "c", 1_600_000, 1, 1, "editor"),
            UniqueSnapshot(3, "d", 2_100_000, 1, 1, "editor"),
            UniqueSnapshot(4, "e", 2_400_000, 1, 1, "editor"),
        ]
        sampled = sample_unique(rows, extra=0)
        hashes = [row.tree_hash for row in sampled]
        self.assertEqual(hashes, ["a", "b", "c", "d", "e"])
        self.assertEqual(tree_hash({"x.py": b"1"}), tree_hash({"x.py": b"1"}))

    def _tmpdir(self):
        import tempfile
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            with tempfile.TemporaryDirectory() as tmp:
                yield Path(tmp)

        return ctx()


if __name__ == "__main__":
    unittest.main()
