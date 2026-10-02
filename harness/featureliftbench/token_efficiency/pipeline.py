"""Pilot sampling and per-run / suite execution with resume support."""

from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from .constants import (
    ANALYSIS_SEED,
    CONFIG_ORDER,
    LIFT_TYPES,
    PILOT_CONFIGS,
    PILOT_FAIL_QUOTA,
    PILOT_PASS_QUOTA,
    RUN_MANIFEST_FIELDS,
    RUN_METRICS_FIELDS,
    METHOD_VERSION,
)
from .evaluate import EvalCache, gates_match, original_gates
from .events import load_events, load_persistence_events, original_steps
from .identity import inspect_identity
from .inventory import inventory_one
from .ledger import build_run_ledger
from .metrics import compute_run_metrics
from .replay import ReplayOutcome, ReplayWorkspace, replay_run, write_timeline
from .scope import OfficialRun, load_official_runs, repo_root
from .util import read_csv, read_json, write_csv, write_json, write_jsonl


def sample_pilot_runs(
    runs: list[OfficialRun],
    *,
    seed: int = ANALYSIS_SEED,
) -> tuple[list[OfficialRun], list[dict[str, Any]]]:
    rng = random.Random(seed)
    selected: list[OfficialRun] = []
    report: list[dict[str, Any]] = []
    by_key: dict[tuple[str, bool, str], list[OfficialRun]] = {}
    for run in runs:
        if run.configuration not in PILOT_CONFIGS:
            continue
        by_key.setdefault((run.configuration, run.final_pass, run.lift_type), []).append(run)
    for configuration in PILOT_CONFIGS:
        for passed, quota in ((True, PILOT_PASS_QUOTA), (False, PILOT_FAIL_QUOTA)):
            for lift in LIFT_TYPES:
                pool = list(by_key.get((configuration, passed, lift), []))
                pool.sort(key=lambda item: item.task_id)
                need = quota[lift]
                taken = pool if len(pool) <= need else rng.sample(pool, need)
                taken = sorted(taken, key=lambda item: item.task_id)
                selected.extend(taken)
                report.append(
                    {
                        "configuration": configuration,
                        "final_pass": passed,
                        "lift_type": lift,
                        "quota": need,
                        "available": len(pool),
                        "sampled": len(taken),
                        "gap": max(0, need - len(taken)),
                        "task_ids": [item.task_id for item in taken],
                        "seed": seed,
                        "rule": "fixed_seed_sample_before_replay; do_not_replace",
                    }
                )
    selected.sort(key=lambda item: (CONFIG_ORDER.index(item.configuration), item.task_id, item.final_pass))
    return selected, report


def sample_other_config_spotchecks(runs: list[OfficialRun]) -> tuple[list[OfficialRun], list[dict[str, Any]]]:
    """One official pass and one fail per remaining configuration.

    Rule: lexicographically first task_id in the official 150. Do not replace
    after replay failure.
    """

    selected: list[OfficialRun] = []
    report: list[dict[str, Any]] = []
    others = [model for model in CONFIG_ORDER if model not in PILOT_CONFIGS]
    for configuration in others:
        for passed in (True, False):
            pool = [
                run
                for run in runs
                if run.configuration == configuration and run.final_pass is passed
            ]
            pool.sort(key=lambda item: item.task_id)
            taken = pool[:1]
            selected.extend(taken)
            report.append(
                {
                    "configuration": configuration,
                    "final_pass": passed,
                    "quota": 1,
                    "available": len(pool),
                    "sampled": len(taken),
                    "gap": max(0, 1 - len(taken)),
                    "task_ids": [item.task_id for item in taken],
                    "rule": "lexicographically_first_official_task_id; do_not_replace",
                }
            )
    return selected, report


def write_pilot_manifest(path: Path, runs: list[OfficialRun], report: list[dict[str, Any]]) -> None:
    rows = []
    for run in runs:
        rows.append(
            {
                "run_id": run.run_id,
                "configuration": run.configuration,
                "task_id": run.task_id,
                "final_pass": run.final_pass,
                "lift_type": run.lift_type,
                "suite_id": run.suite_id,
                "source_run_dir": run.source_run_dir,
                "seed": ANALYSIS_SEED,
            }
        )
    write_csv(
        path,
        rows,
        (
            "run_id",
            "configuration",
            "task_id",
            "final_pass",
            "lift_type",
            "suite_id",
            "source_run_dir",
            "seed",
        ),
    )
    write_json(path.with_name("pilot_sampling_report.json"), report)


def process_one_run(
    run: OfficialRun,
    *,
    output_dir: Path,
    cache: EvalCache,
    cas_dir: Path,
    work_root: Path,
    root: Path,
    use_docker: bool = True,
    resume: bool = True,
    evaluate_states: bool = True,
) -> dict[str, Any]:
    run_dir = output_dir / "runs" / run.configuration / run.task_id
    metrics_path = run_dir / "metrics.json"
    if resume and metrics_path.is_file():
        try:
            existing = read_json(metrics_path)
            if (existing.get("run_id") == run.run_id
                    and existing.get("method_version") == METHOD_VERSION
                    and existing.get("replay_status") != "running"):
                print(f"[token-efficiency] resume-skip {run.run_id}", flush=True)
                return existing
        except (OSError, ValueError):
            pass
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[token-efficiency] start {run.run_id}", flush=True)
    identity = inspect_identity(run)
    write_json(run_dir / "identity.json", identity.as_dict())
    mapped = Path(run.mapped_run_dir)
    events_path = mapped / "agent" / "openhands_events.jsonl"
    if events_path.is_file() and events_path.stat().st_size > 0:
        events = load_events(events_path)
    else:
        events = load_persistence_events(mapped / "agent" / "openhands_persistence")
    ledger = build_run_ledger(
        configuration=run.configuration,
        audit_path=mapped / "agent" / "context_audit.jsonl",
        usage_path=mapped / "agent" / "usage.json",
        events=events,
    )
    write_jsonl(run_dir / "calls.jsonl", [call.to_json() for call in ledger.calls])
    write_json(
        run_dir / "ledger.json",
        {
            "accounting_basis": ledger.accounting_basis,
            "token_usage_status": ledger.token_usage_status,
            "token_alignment_status": ledger.token_alignment_status,
            "total_tokens": ledger.total_tokens,
            "main_table_tokens": ledger.main_table_tokens,
            "usage_json_total": ledger.usage_json_total,
            "ledger_minus_usage": ledger.ledger_minus_usage,
            "missing_reason": ledger.missing_reason,
            "notes": ledger.notes,
        },
    )

    replay: ReplayOutcome | None = None
    evaluations: dict[str, Any] = {}
    final_eval_matches = None
    if identity.status == "identity_conflict":
        metrics = compute_run_metrics(
            run=run,
            identity_status=identity.status,
            ledger=ledger,
            replay=None,
            evaluations={},
            final_eval_matches=None,
        )
        write_json(metrics_path, metrics.to_row())
        return metrics.to_row()

    replay = replay_run(
        run,
        ledger=ledger,
        cas_dir=cas_dir,
        work_root=work_root,
        root=root,
        use_docker=use_docker,
    )
    write_timeline(run_dir / "artifact_timeline.jsonl", replay.timeline)
    write_json(
        run_dir / "replay.json",
        {
            "reconstruction_status": replay.reconstruction_status,
            "full_timeline_covered": replay.full_timeline_covered,
            "last_hash": replay.last_hash,
            "disk_hash": replay.disk_hash,
            "last_matches_disk": replay.last_matches_disk,
            "unique_hashes": replay.unique_hashes,
            "editor_writes": replay.editor_writes,
            "terminal_runs": replay.terminal_runs,
            "terminal_errors": replay.terminal_errors,
            "unmatched_tools": replay.unmatched_tools,
            "error": replay.error,
        },
    )

    if evaluate_states and replay.disk_hash:
        original_eval = cache.evaluate_path(
            run=run,
            artifact_hash=replay.disk_hash,
            submission=mapped / "submission",
            label="original_final",
        )
        evaluations[replay.disk_hash] = original_eval
        write_json(run_dir / "final_reeval.json", original_eval.to_row())
        final_eval_matches = gates_match(
            {
                "functional_pass": original_eval.functional_pass,
                "build_pass": original_eval.build_pass,
                "public_pass": original_eval.public_pass,
                "hidden_pass": original_eval.hidden_pass,
                "isolation_pass": original_eval.isolation_pass,
            },
            original_gates(run),
        )
        if replay.last_hash and replay.last_hash != replay.disk_hash and replay.last_hash in replay.unique_hashes:
            evaluations[replay.last_hash] = cache.evaluate_hash(
                run=run, artifact_hash=replay.last_hash, cas_dir=cas_dir
            )

    if evaluate_states:
        for digest in replay.unique_hashes:
            if digest in evaluations:
                continue
            evaluations[digest] = cache.evaluate_hash(
                run=run, artifact_hash=digest, cas_dir=cas_dir
            )
        write_json(
            run_dir / "snapshot_evaluations.json",
            {digest: item.to_row() for digest, item in evaluations.items()},
        )
        for state in replay.timeline:
            evaluation = evaluations.get(state.artifact_hash)
            if evaluation is not None:
                state.eval_key = evaluation.eval_key
        write_timeline(run_dir / "artifact_timeline.jsonl", replay.timeline)

    metrics = compute_run_metrics(
        run=run,
        identity_status=identity.status,
        ledger=ledger,
        replay=replay,
        evaluations=evaluations,
        final_eval_matches=final_eval_matches,
    )
    write_json(metrics_path, metrics.to_row())
    print(
        f"[token-efficiency] done {run.run_id} replay={metrics.to_row().get('replay_status')} "
        f"sufficiency={metrics.to_row().get('sufficiency_status')} "
        f"eval_match={metrics.to_row().get('final_eval_matches')}",
        flush=True,
    )
    return metrics.to_row()


def run_suite(
    runs: list[OfficialRun],
    *,
    output_dir: Path,
    workers: int = 2,
    resume: bool = True,
    use_docker: bool = True,
    evaluate_states: bool = True,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    base = (root or repo_root()).resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cas_dir = output_dir.parent / "cas"
    cache = EvalCache(output_dir.parent / "eval_cache", root=base)
    work_root = output_dir / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "environment.json",
        {
            "eval_code_hash": cache.eval_code_hash,
            "image_digest": cache.image_digest,
            "image_available": cache.image_available,
            "n_assigned": len(runs),
        },
    )
    rows: list[dict[str, Any]] = []
    if workers <= 1:
        for run in runs:
            rows.append(
                process_one_run(
                    run,
                    output_dir=output_dir,
                    cache=cache,
                    cas_dir=cas_dir,
                    work_root=work_root,
                    root=base,
                    use_docker=use_docker,
                    resume=resume,
                    evaluate_states=evaluate_states,
                )
            )
            _write_metrics_table(output_dir, rows, runs)
        return rows

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                process_one_run,
                run,
                output_dir=output_dir,
                cache=cache,
                cas_dir=cas_dir,
                work_root=work_root,
                root=base,
                use_docker=use_docker,
                resume=resume,
                evaluate_states=evaluate_states,
            ): run
            for run in runs
        }
        done: dict[str, dict[str, Any]] = {}
        for future in as_completed(futures):
            run = futures[future]
            try:
                done[run.run_id] = future.result()
            except Exception as exc:  # noqa: BLE001
                row = {
                    "run_id": run.run_id,
                    "configuration": run.configuration,
                    "task_id": run.task_id,
                    "lift_type": run.lift_type,
                    "final_pass": run.final_pass,
                    "replay_status": "error",
                    "sufficiency_status": "unresolved",
                    "missing_reason": f"{type(exc).__name__}: {exc}",
                    "include_psf_primary": False,
                    "include_effort": False,
                    "include_failure_history": False,
                }
                run_dir = output_dir / "runs" / run.configuration / run.task_id
                run_dir.mkdir(parents=True, exist_ok=True)
                write_json(run_dir / "metrics.json", row)
                done[run.run_id] = row
            rows = [done[item.run_id] for item in runs if item.run_id in done]
            _write_metrics_table(output_dir, rows, runs)
    rows = [done[item.run_id] for item in runs]
    _write_metrics_table(output_dir, rows, runs)
    return rows


def parse_spotcheck_runs(
    runs: list[OfficialRun],
    *,
    output_dir: Path,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Parse identity, events, and token ledgers without Docker replay or eval."""

    base = (root or repo_root()).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for run in runs:
        mapped = Path(run.mapped_run_dir)
        identity = inspect_identity(run)
        events_path = mapped / "agent" / "openhands_events.jsonl"
        if events_path.is_file() and events_path.stat().st_size > 0:
            events = load_events(events_path)
            event_source = "openhands_events.jsonl"
        else:
            events = load_persistence_events(mapped / "agent" / "openhands_persistence")
            event_source = "openhands_persistence" if events else ""
        from .events import pair_completions, count_event_kinds, count_tools

        completions, pair_stats = pair_completions(events) if events else ([], {})
        ledger = build_run_ledger(
            configuration=run.configuration,
            audit_path=mapped / "agent" / "context_audit.jsonl",
            usage_path=mapped / "agent" / "usage.json",
            events=events,
        )
        kinds = {item.kind for item in events}
        tools = sorted({item.tool_name for item in events if item.tool_name})
        row = {
            "run_id": run.run_id,
            "configuration": run.configuration,
            "task_id": run.task_id,
            "final_pass": run.final_pass,
            "identity_status": identity.status,
            "event_source": event_source,
            "n_events": len(events),
            "event_kinds": sorted(kinds),
            "tools": tools,
            "n_completions": len(completions),
            "unmatched_observations": pair_stats.get("unmatched_observations"),
            "unmatched_actions": pair_stats.get("unmatched_actions"),
            "token_usage_status": ledger.token_usage_status,
            "token_alignment_status": ledger.token_alignment_status,
            "total_tokens": ledger.total_tokens,
            "usage_json_total": ledger.usage_json_total,
            "ledger_minus_usage": ledger.ledger_minus_usage,
            "missing_reason": ledger.missing_reason,
            "notes": ledger.notes,
            "has_tool_call_id": any(item.tool_call_id for item in events),
            "has_llm_response_id": any(item.llm_response_id for item in events),
            "multi_tool_responses": _multi_tool_count(events),
        }
        rows.append(row)
        write_json(output_dir / "runs" / f"{run.configuration}__{run.task_id}.json", row)
    write_json(output_dir / "spotcheck_parse.json", rows)
    write_csv(
        output_dir / "spotcheck_parse.csv",
        rows,
        (
            "run_id",
            "configuration",
            "task_id",
            "final_pass",
            "identity_status",
            "n_events",
            "n_completions",
            "unmatched_observations",
            "token_usage_status",
            "token_alignment_status",
            "total_tokens",
            "missing_reason",
            "multi_tool_responses",
            "has_tool_call_id",
            "has_llm_response_id",
        ),
    )
    return rows


def _multi_tool_count(events: list) -> int:
    counts: dict[str, int] = {}
    for event in events:
        if getattr(event, "kind", "") != "ActionEvent":
            continue
        response = event.llm_response_id
        if not response:
            continue
        counts[response] = counts.get(response, 0) + 1
    return sum(1 for value in counts.values() if value > 1)


def progress_counts(output_dir: Path, assigned: int = 900) -> dict[str, Any]:
    done = list((output_dir / "runs").glob("*/*/metrics.json")) if (output_dir / "runs").is_dir() else []
    by_config: dict[str, int] = {}
    for path in done:
        by_config[path.parent.parent.name] = by_config.get(path.parent.parent.name, 0) + 1
    return {
        "assigned": assigned,
        "completed": len(done),
        "remaining": assigned - len(done),
        "by_configuration": by_config,
        "output_dir": str(output_dir),
    }


def collect_run_metrics(output_dir: Path, runs: list[OfficialRun]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        path = output_dir / "runs" / run.configuration / run.task_id / "metrics.json"
        if path.is_file():
            try:
                rows.append(read_json(path))
                continue
            except (OSError, ValueError):
                pass
        rows.append(
            {
                "run_id": run.run_id,
                "configuration": run.configuration,
                "task_id": run.task_id,
                "lift_type": run.lift_type,
                "final_pass": run.final_pass,
                "identity_status": "unresolved",
                "replay_status": "unresolved",
                "sufficiency_status": "unresolved",
                "include_psf_primary": False,
                "include_effort": False,
                "include_failure_history": False,
                "missing_reason": "not_processed",
            }
        )
    return rows


def _write_metrics_table(
    output_dir: Path, rows: list[dict[str, Any]], assigned: list[OfficialRun]
) -> None:
    by_id = {row.get("run_id"): row for row in rows}
    ordered = []
    for run in assigned:
        if run.run_id in by_id:
            ordered.append(by_id[run.run_id])
        else:
            ordered.append({"run_id": run.run_id, "configuration": run.configuration, "task_id": run.task_id})
    write_csv(output_dir / "run_metrics.csv", ordered, RUN_METRICS_FIELDS)
    write_csv(
        output_dir / "run_manifest.csv",
        [
            {
                "run_id": run.run_id,
                "configuration": run.configuration,
                "task_id": run.task_id,
                "suite_id": run.suite_id,
                "source_run_dir": run.source_run_dir,
                "mapped_run_dir": run.mapped_run_dir,
                "final_pass": run.final_pass,
                "lift_type": run.lift_type,
                "identity_status": (by_id.get(run.run_id) or {}).get("identity_status", ""),
                "events_available": "",
                "call_usage_available": "",
                "final_eval_available": "",
                "initial_state_available": "",
                "final_artifact_available": "",
                "path_identity_ok": "",
            }
            for run in assigned
        ],
        RUN_MANIFEST_FIELDS,
    )
