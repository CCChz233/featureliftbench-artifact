from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from featureliftbench.token_efficiency.artifacts import empty_artifact_hash, hash_tree, write_entries
from featureliftbench.token_efficiency.artifacts import ArtifactEntry, artifact_hash
from featureliftbench.token_efficiency.constants import ANALYSIS_SEED
from featureliftbench.token_efficiency.evaluate import EvalCache, _eval_status, _gates
from featureliftbench.token_efficiency.events import load_events, pair_completions
from featureliftbench.token_efficiency.ledger import build_run_ledger, load_audit_calls
from featureliftbench.token_efficiency.metrics import compute_run_metrics
from featureliftbench.token_efficiency.pipeline import sample_pilot_runs
from featureliftbench.token_efficiency.replay import ScriptedTerminal, replay_from_events, ReplayWorkspace
from featureliftbench.token_efficiency.scope import OfficialRun
from featureliftbench.token_efficiency.evaluate import SnapshotEvaluation
from featureliftbench.token_efficiency.replay import ReplayOutcome, TimelineState
from featureliftbench.token_efficiency.ledger import RunLedger, CallRecord
from featureliftbench.token_efficiency.constants import ACCOUNTING_TOTAL


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _action(event_id: str, call_id: str, response_id: str, tool: str, command: str, ts: str) -> dict:
    return {
        "id": event_id,
        "kind": "ActionEvent",
        "tool_name": tool,
        "tool_call_id": call_id,
        "llm_response_id": response_id,
        "timestamp": ts,
        "action": {"command": command, "path": "/flb/workspace/submission/featurelifted/pkg.py"},
        "tool_call": {"id": call_id, "name": tool},
    }


def _obs(event_id: str, action_id: str, call_id: str, tool: str, ts: str, observation: dict) -> dict:
    return {
        "id": event_id,
        "kind": "ObservationEvent",
        "action_id": action_id,
        "tool_call_id": call_id,
        "tool_name": tool,
        "timestamp": ts,
        "observation": observation,
    }


class TokenEfficiencyTests(unittest.TestCase):
    def test_mixed_missing_usage_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.jsonl"
            _write_jsonl(audit, [
                {"timestamp": "2026-09-16T00:00:00Z", "prompt_tokens": 80,
                 "completion_tokens": 20, "total_tokens": 100, "status": 200},
                {"timestamp": "2026-09-16T00:00:02Z", "prompt_tokens": None,
                 "completion_tokens": None, "total_tokens": None, "status": 200},
            ])
            ledger = build_run_ledger(configuration="gpt-oss-120b", audit_path=audit,
                                      usage_path=root / "absent.json", events=[])
            self.assertEqual(ledger.token_usage_status, "partial")
            self.assertIsNone(ledger.total_tokens)

    def test_candidate_prefix_cannot_promote_bounded_alignment(self) -> None:
        from types import SimpleNamespace
        from featureliftbench.token_efficiency.ledger import tokens_for_completion
        ledger = RunLedger([], ACCOUNTING_TOTAL, "complete", "bounded", 100, 100, 100, 0,
                           response_to_call={"response": "call"}, cumulative_by_call={"call": 30},
                           cumulative_bounds_by_call={"call": (30, 30)})
        result = tokens_for_completion(ledger, SimpleNamespace(llm_response_id="response"), set())
        self.assertEqual(result, (None, 0, 100, "bounded"))

    def test_summary_uses_post_fraction_and_escapes_percent(self) -> None:
        from unittest.mock import patch
        from featureliftbench.token_efficiency.constants import CONFIG_ORDER
        from featureliftbench.token_efficiency.summarize import summarize_suite
        runs = [_run(model, "demo", True) for model in CONFIG_ORDER]
        rows = [{"run_id": r.run_id, "configuration": r.configuration, "task_id": r.task_id,
                 "final_pass": True, "include_psf_primary": True, "include_effort": True,
                 "first_pass_fraction": .25, "post_sufficiency_fraction": .75,
                 "total_tokens": 100, "post_sufficiency_tokens": 75, "lift_type": "Direct"}
                for r in runs]
        with tempfile.TemporaryDirectory() as tmp:
            with patch("featureliftbench.token_efficiency.summarize._write_figures", return_value={}):
                output = summarize_suite(metrics_rows=rows, runs=runs, output_dir=Path(tmp))
            self.assertEqual(output["summary"][0]["median_psf"], .75)
            self.assertIn(r"75.0\%", (Path(tmp)/"paper_ready/efficiency_table.tex").read_text())

    def test_dependency_install_failure_is_not_artifact_failure(self) -> None:
        status = _eval_status({"status": "failed", "build_pass": False,
                               "errors": ["dependency installation failed"]})
        self.assertEqual(status, "infra_error")
        self.assertIsNone(_gates({"build_pass": False}, status)["functional_pass"])

    def test_batch_tool_calls_pair_by_tool_call_id_not_last_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            _write_jsonl(
                path,
                [
                    _action("a1", "c1", "r1", "file_editor", "create", "2026-09-16T00:00:00Z"),
                    _action("a2", "c2", "r1", "file_editor", "create", "2026-09-16T00:00:00Z"),
                    _obs(
                        "o1",
                        "a2",
                        "c2",
                        "file_editor",
                        "2026-09-16T00:00:01Z",
                        {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/b.py",
                            "is_error": False,
                            "new_content": "B = 2\n",
                        },
                    ),
                    _obs(
                        "o2",
                        "a1",
                        "c1",
                        "file_editor",
                        "2026-09-16T00:00:02Z",
                        {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/a.py",
                            "is_error": False,
                            "new_content": "A = 1\n",
                        },
                    ),
                ],
            )
            completions, stats = pair_completions(load_events(path))
            self.assertEqual(stats["unmatched_observations"], 0)
            by_call = {item.tool_call_id: item.path for item in completions}
            self.assertEqual(by_call["c2"].endswith("b.py"), True)
            self.assertEqual(by_call["c1"].endswith("a.py"), True)

    def test_editor_does_not_crash_writing_directory_or_null_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = ReplayWorkspace(Path(tmp))
            sandbox.workspace.mkdir(parents=True)
            sandbox.tmp.mkdir(parents=True)
            sandbox.submission.mkdir(parents=True)
            lifted = sandbox.submission / "featurelifted"
            lifted.mkdir()
            self.assertFalse(
                sandbox.apply_editor("/flb/workspace/submission/featurelifted", "not a file\n")
            )
            self.assertTrue(lifted.is_dir())
            self.assertIsNone(sandbox.resolve_container_path("/flb/workspace/foo\x00bar.py"))
            from featureliftbench.token_efficiency.events import ToolCompletion
            from featureliftbench.token_efficiency.replay import _apply_completion

            completion = ToolCompletion(
                event_index=1,
                event_id="e",
                action_event_id="a",
                tool_call_id="c",
                llm_response_id="r",
                tool_name="terminal",
                timestamp=None,
                command="rm -rf /flb/workspace/submission/featurelifted/\x00bad",
                path="",
                is_error=False,
                mutation_kind="delete",
                editor_command="",
                new_content=None,
                observation={},
            )
            mutated, status, kind = _apply_completion(sandbox, None, completion)
            self.assertEqual(status, "unresolved")
            self.assertFalse(mutated)

    def test_failed_editor_and_empty_and_rollback_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "src.py").write_text("SRC=1\n", encoding="utf-8")
            (root / "TASK.md").write_text("# task\n", encoding="utf-8")
            (root / "metadata.json").write_text('{"task_id":"demo"}\n', encoding="utf-8")
            events = root / "events.jsonl"
            _write_jsonl(
                events,
                [
                    _action("a0", "c0", "r0", "file_editor", "create", "2026-09-16T00:00:00Z"),
                    _obs(
                        "o0",
                        "a0",
                        "c0",
                        "file_editor",
                        "2026-09-16T00:00:01Z",
                        {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/pkg.py",
                            "is_error": True,
                            "new_content": "NOPE\n",
                        },
                    ),
                    _action("a1", "c1", "r1", "file_editor", "create", "2026-09-16T00:00:02Z"),
                    _obs(
                        "o1",
                        "a1",
                        "c1",
                        "file_editor",
                        "2026-09-16T00:00:03Z",
                        {
                            "command": "create",
                            "path": "/flb/workspace/submission/featurelifted/pkg.py",
                            "is_error": False,
                            "new_content": "A = 1\n",
                        },
                    ),
                    _action("a2", "c2", "r2", "file_editor", "str_replace", "2026-09-16T00:00:04Z"),
                    _obs(
                        "o2",
                        "a2",
                        "c2",
                        "file_editor",
                        "2026-09-16T00:00:05Z",
                        {
                            "command": "str_replace",
                            "path": "/flb/workspace/submission/featurelifted/pkg.py",
                            "is_error": False,
                            "new_content": "B = 2\n",
                        },
                    ),
                    _action("a3", "c3", "r3", "file_editor", "str_replace", "2026-09-16T00:00:06Z"),
                    _obs(
                        "o3",
                        "a3",
                        "c3",
                        "file_editor",
                        "2026-09-16T00:00:07Z",
                        {
                            "command": "str_replace",
                            "path": "/flb/workspace/submission/featurelifted/pkg.py",
                            "is_error": False,
                            "new_content": "A = 1\n",
                        },
                    ),
                    _action("a4", "c4", "r4", "file_editor", "delete", "2026-09-16T00:00:08Z"),
                    _obs(
                        "o4",
                        "a4",
                        "c4",
                        "file_editor",
                        "2026-09-16T00:00:09Z",
                        {
                            "command": "delete",
                            "path": "/flb/workspace/submission/featurelifted/pkg.py",
                            "is_error": False,
                        },
                    ),
                ],
            )
            ledger = _empty_ledger()
            result = replay_from_events(
                events_path=events,
                repo_src=repo,
                task_md=root / "TASK.md",
                metadata=root / "metadata.json",
                ledger=ledger,
                terminal=ScriptedTerminal(),
            )
            hashes = [item.artifact_hash for item in result.timeline]
            kinds = [item.mutation_kind for item in result.timeline]
            self.assertEqual(kinds[0], "initial")
            self.assertIn("editor_write", kinds)
            self.assertIn("delete", kinds)
            self.assertGreaterEqual(len(hashes), 4)
            self.assertEqual(hashes[1], hashes[3])
            self.assertNotEqual(hashes[1], hashes[2])
            self.assertEqual(result.timeline[1].artifact_hash, result.timeline[3].artifact_hash)
            self.assertEqual(kinds[-1], "delete")
            self.assertNotEqual(hashes[-1], hashes[1])

    def test_symlink_and_empty_dir_are_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "submission"
            root.mkdir()
            (root / "featurelifted").mkdir()
            (root / "featurelifted" / "empty").mkdir()
            (root / "featurelifted" / "file.py").write_text("x\n", encoding="utf-8")
            (root / "featurelifted" / "link.py").symlink_to("file.py")
            digest = hash_tree(root)
            self.assertNotEqual(digest, empty_artifact_hash())
            other = Path(tmp) / "other"
            write_entries(
                other,
                [
                    ArtifactEntry("featurelifted", "dir", "040000", b""),
                    ArtifactEntry("featurelifted/empty", "dir", "040000", b""),
                    ArtifactEntry("featurelifted/file.py", "file", "100644", b"x\n"),
                    ArtifactEntry("featurelifted/link.py", "symlink", "120000", b"file.py"),
                ],
            )
            self.assertEqual(digest, hash_tree(other))

    def test_duplicate_audit_lines_are_dropped_retries_kept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            _write_jsonl(
                path,
                [
                    {
                        "timestamp": "2026-09-16T00:00:00Z",
                        "model": "m",
                        "path": "/v1/chat/completions",
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "usage_verified": True,
                        "status": 200,
                    },
                    {
                        "timestamp": "2026-09-16T00:00:00Z",
                        "model": "m",
                        "path": "/v1/chat/completions",
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "usage_verified": True,
                        "status": 200,
                    },
                    {
                        "timestamp": "2026-09-16T00:00:01Z",
                        "model": "m",
                        "path": "/v1/chat/completions",
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "usage_verified": True,
                        "status": 200,
                    },
                    {
                        "timestamp": "2026-09-16T00:00:02Z",
                        "model": "m",
                        "path": "/v1/chat/completions",
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": None,
                        "usage_verified": False,
                        "status": 500,
                    },
                ],
            )
            calls = load_audit_calls(path)
            included = [call for call in calls if call.inclusion_status == "included"]
            duplicates = [call for call in calls if call.inclusion_status == "duplicate"]
            missing = [call for call in calls if call.inclusion_status == "excluded_missing_usage"]
            self.assertEqual(len(included), 2)
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(len(missing), 1)

    def test_eval_error_is_not_functional_fail(self) -> None:
        self.assertEqual(_eval_status({"status": "error", "errors": ["boom"]}), "error")
        gates = _gates({"status": "error", "build_pass": False}, "error")
        self.assertIsNone(gates["functional_pass"])
        self.assertIsNone(gates["build_pass"])
        ok = _gates(
            {
                "status": "failed",
                "build_pass": True,
                "public_tests_pass": True,
                "hidden_tests_pass": False,
                "isolation_pass": True,
                "scores": {"functional_gate": 0.0},
            },
            "ok",
        )
        self.assertFalse(ok["functional_pass"])
        self.assertTrue(ok["build_pass"])

    def test_eval_cache_keys_include_configuration_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = object.__new__(EvalCache)
            cache.cache_dir = Path(tmp)
            cache.root = Path(tmp)
            cache.eval_code_hash = "code"
            cache.image_digest = "sha256:aaa"
            cache._capsule_hashes = {"taskA": "capA", "taskB": "capB"}
            cache._lock = __import__("threading").Lock()
            key_a = EvalCache.make_eval_key(cache, "taskA", "hash1")
            key_b = EvalCache.make_eval_key(cache, "taskB", "hash1")
            key_c = EvalCache.make_eval_key(cache, "taskA", "hash2")
            self.assertNotEqual(key_a, key_b)
            self.assertNotEqual(key_a, key_c)

    def test_first_pass_survives_later_failure(self) -> None:
        run = _run("deepseek-v4-pro", "demo", True)
        hashes = ["empty", "passA", "failB", "passA"]
        timeline = [
            TimelineState(0, "initial", "", None, hashes[0], "exact", "initial", "ok", "exact", ACCOUNTING_TOTAL, 0, 0, 0),
            TimelineState(1, "e1", "c1", 1.0, hashes[1], "exact", "editor_write", "ok", "exact", ACCOUNTING_TOTAL, 100, 100, 100),
            TimelineState(2, "e2", "c2", 2.0, hashes[2], "exact", "editor_write", "ok", "exact", ACCOUNTING_TOTAL, 200, 200, 200),
            TimelineState(3, "e3", "c3", 3.0, hashes[3], "exact", "editor_write", "ok", "exact", ACCOUNTING_TOTAL, 300, 300, 300),
        ]
        evaluations = {
            "empty": _eval("empty", False),
            "passA": _eval("passA", True),
            "failB": _eval("failB", False),
        }
        replay = ReplayOutcome(
            timeline=timeline,
            unique_hashes=list(dict.fromkeys(hashes)),
            last_hash="passA",
            disk_hash="passA",
            last_matches_disk=True,
            reconstruction_status="ok",
            full_timeline_covered=True,
            editor_writes=3,
            terminal_runs=0,
            terminal_errors=0,
            unmatched_tools=0,
        )
        ledger = RunLedger(
            calls=[],
            accounting_basis=ACCOUNTING_TOTAL,
            token_usage_status="complete",
            token_alignment_status="exact",
            total_tokens=300,
            main_table_tokens=300,
            usage_json_total=300,
            ledger_minus_usage=0,
        )
        metrics = compute_run_metrics(
            run=run,
            identity_status="ok",
            ledger=ledger,
            replay=replay,
            evaluations=evaluations,
            final_eval_matches=True,
        )
        row = metrics.to_row()
        self.assertEqual(row["first_pass_state_index"], 1)
        self.assertEqual(row["first_pass_hash"], "passA")
        self.assertTrue(row["post_sufficiency_failure_seen"])
        self.assertEqual(row["post_sufficiency_mutations"], 2)
        self.assertTrue(row["include_psf_primary"])
        self.assertAlmostEqual(row["first_pass_fraction"], 100 / 300)
        self.assertAlmostEqual(row["post_sufficiency_fraction"], 200 / 300)

    def test_never_sufficient_is_not_zero(self) -> None:
        run = _run("deepseek-v4-pro", "demo", False)
        timeline = [
            TimelineState(0, "initial", "", None, "h0", "exact", "initial", "ok", "exact", ACCOUNTING_TOTAL, 0, 0, 0),
            TimelineState(1, "e1", "c1", 1.0, "h1", "exact", "editor_write", "ok", "exact", ACCOUNTING_TOTAL, 50, 50, 50),
        ]
        evaluations = {"h0": _eval("h0", False), "h1": _eval("h1", False)}
        replay = ReplayOutcome(
            timeline=timeline,
            unique_hashes=["h0", "h1"],
            last_hash="h1",
            disk_hash="h1",
            last_matches_disk=True,
            reconstruction_status="ok",
            full_timeline_covered=True,
            editor_writes=1,
            terminal_runs=0,
            terminal_errors=0,
            unmatched_tools=0,
        )
        ledger = RunLedger(
            calls=[],
            accounting_basis=ACCOUNTING_TOTAL,
            token_usage_status="complete",
            token_alignment_status="exact",
            total_tokens=50,
            main_table_tokens=50,
            usage_json_total=50,
            ledger_minus_usage=0,
        )
        row = compute_run_metrics(
            run=run,
            identity_status="ok",
            ledger=ledger,
            replay=replay,
            evaluations=evaluations,
            final_eval_matches=True,
        ).to_row()
        self.assertEqual(row["sufficiency_status"], "never_sufficient")
        self.assertIsNone(row["first_pass_fraction"])
        self.assertFalse(row["ever_pass_final_fail"])
        self.assertFalse(row["include_psf_primary"])

    def test_equal_token_bounds_promote_to_exact(self) -> None:
        run = _run("deepseek-v4-pro", "demo", True)
        timeline = [
            TimelineState(0, "initial", "", None, "h0", "exact", "initial", "ok", "bounded", ACCOUNTING_TOTAL, None, 0, 0),
            TimelineState(1, "e1", "c1", 1.0, "h1", "exact", "editor_write", "ok", "bounded", ACCOUNTING_TOTAL, None, 120, 120),
        ]
        evaluations = {"h0": _eval("h0", False), "h1": _eval("h1", True)}
        replay = ReplayOutcome(
            timeline=timeline,
            unique_hashes=["h0", "h1"],
            last_hash="h1",
            disk_hash="h1",
            last_matches_disk=True,
            reconstruction_status="ok",
            full_timeline_covered=True,
            editor_writes=1,
            terminal_runs=0,
            terminal_errors=0,
            unmatched_tools=0,
        )
        ledger = RunLedger(
            calls=[],
            accounting_basis=ACCOUNTING_TOTAL,
            token_usage_status="complete",
            token_alignment_status="exact",
            total_tokens=200,
            main_table_tokens=200,
            usage_json_total=200,
            ledger_minus_usage=0,
        )
        row = compute_run_metrics(
            run=run,
            identity_status="ok",
            ledger=ledger,
            replay=replay,
            evaluations=evaluations,
            final_eval_matches=True,
        ).to_row()
        self.assertEqual(row["sufficiency_status"], "exact")
        self.assertEqual(row["first_pass_tokens"], 120)
        self.assertTrue(row["include_psf_primary"])
        self.assertAlmostEqual(row["post_sufficiency_fraction"], 80 / 200)

    def test_incomplete_timeline_stays_bounded_even_if_bounds_match(self) -> None:
        run = _run("deepseek-v4-pro", "demo", True)
        timeline = [
            TimelineState(0, "initial", "", None, "h0", "exact", "initial", "ok", "exact", ACCOUNTING_TOTAL, 0, 0, 0),
            TimelineState(1, "e1", "c1", 1.0, "h1", "exact", "editor_write", "ok", "exact", ACCOUNTING_TOTAL, 90, 90, 90),
        ]
        evaluations = {"h0": _eval("h0", False), "h1": _eval("h1", True)}
        replay = ReplayOutcome(
            timeline=timeline,
            unique_hashes=["h0", "h1"],
            last_hash="h1",
            disk_hash="h1",
            last_matches_disk=False,
            reconstruction_status="partial",
            full_timeline_covered=False,
            editor_writes=1,
            terminal_runs=0,
            terminal_errors=0,
            unmatched_tools=0,
        )
        ledger = RunLedger(
            calls=[],
            accounting_basis=ACCOUNTING_TOTAL,
            token_usage_status="complete",
            token_alignment_status="exact",
            total_tokens=90,
            main_table_tokens=90,
            usage_json_total=90,
            ledger_minus_usage=0,
        )
        row = compute_run_metrics(
            run=run,
            identity_status="ok",
            ledger=ledger,
            replay=replay,
            evaluations=evaluations,
            final_eval_matches=True,
        ).to_row()
        self.assertEqual(row["sufficiency_status"], "bounded")
        self.assertFalse(row["include_psf_primary"])
        self.assertEqual(row["exclusion_reason_psf_primary"], "timeline_incomplete")

    def test_null_audit_usage_is_per_call_usage_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "context_audit.jsonl"
            _write_jsonl(
                audit,
                [
                    {
                        "timestamp": "2026-09-16T00:00:00Z",
                        "model": "gpt-5.6-luna",
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": None,
                    }
                ],
            )
            ledger = build_run_ledger(
                configuration="gpt-5.6-luna",
                audit_path=audit,
                usage_path=Path(tmp) / "usage.json",
                events=[],
            )
            self.assertEqual(ledger.missing_reason, "per_call_usage_null")
            self.assertEqual(ledger.token_usage_status, "missing")
            self.assertIsNone(ledger.total_tokens)

    def test_pilot_sampling_is_deterministic_and_does_not_replace(self) -> None:
        runs = []
        for model in ("deepseek-v4-pro", "deepseek-v4-flash"):
            for lift in ("Direct", "Adapted", "Composite"):
                for passed in (True, False):
                    for index in range(4):
                        runs.append(
                            _run(
                                model,
                                f"{model}-{lift}-{passed}-{index}",
                                passed,
                                lift_type=lift,
                            )
                        )
        first, report = sample_pilot_runs(runs, seed=ANALYSIS_SEED)
        second, _ = sample_pilot_runs(runs, seed=ANALYSIS_SEED)
        self.assertEqual([item.run_id for item in first], [item.run_id for item in second])
        self.assertEqual(len(first), 20)
        self.assertTrue(all(item["gap"] == 0 for item in report))


def _run(model: str, task_id: str, passed: bool, lift_type: str = "Direct") -> OfficialRun:
    return OfficialRun(
        run_id=f"{model}/{task_id}",
        configuration=model,
        display_name=model,
        short_name=model,
        task_id=task_id,
        suite_id="suite",
        source_run_dir=f"experiments/{model}/{task_id}",
        mapped_run_dir=f"/tmp/{model}/{task_id}",
        final_pass=passed,
        lift_type=lift_type,
        official_tokens=100,
        original_steps=10,
        usage_source="usage.json",
        usage_unverified=False,
        eval_docker_image="featureliftbench-eval:python200-prime-212930ea",
        freeze_id="freeze",
        build_pass=passed,
        public_pass=passed,
        hidden_pass=passed,
        isolation_pass=passed,
    )


def _eval(digest: str, passed: bool) -> SnapshotEvaluation:
    return SnapshotEvaluation(
        run_id="r",
        task_id="demo",
        artifact_hash=digest,
        eval_key="k",
        image_digest="sha",
        task_capsule_hash="cap",
        eval_code_hash="code",
        eval_status="ok",
        functional_pass=passed,
        build_pass=True,
        public_pass=passed,
        hidden_pass=passed,
        isolation_pass=True,
        retry_count=0,
        result_path="",
        log_path="",
        cached=False,
    )


def _empty_ledger() -> RunLedger:
    return RunLedger(
        calls=[],
        accounting_basis=ACCOUNTING_TOTAL,
        token_usage_status="missing",
        token_alignment_status="unresolved",
        total_tokens=None,
        main_table_tokens=None,
        usage_json_total=None,
        ledger_minus_usage=None,
        missing_reason="test",
    )


if __name__ == "__main__":
    unittest.main()
