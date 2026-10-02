"""Phase A: read-only coverage inventory of the official 900 runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .artifacts import hash_tree
from .constants import (
    CONFIG_ORDER,
    EVAL_CODE_RELATIVE,
    PINNED_EVAL_IMAGE,
    PINNED_REPLAY_IMAGE,
    RUN_MANIFEST_FIELDS,
)
from .events import (
    classify_terminal_command,
    count_event_kinds,
    count_tools,
    load_events,
    load_persistence_events,
    pair_completions,
)
from .identity import inspect_identity
from .ledger import build_run_ledger, call_usage_available
from .scope import OfficialRun, load_official_runs, official_pass_counts, repo_root
from .util import (
    docker_image_identity,
    git_commit,
    git_dirty,
    hash_files,
    read_json,
    sha256_file,
    write_csv,
    write_json,
)


def inventory_official_runs(
    *,
    output_dir: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    base = (root or repo_root()).resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = load_official_runs(base)
    env = collect_environment(base)
    manifest_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    event_kinds = Counter()
    tools = Counter()
    mutations = Counter()
    coverage_rows: list[dict[str, Any]] = []
    per_config = {model: _empty_coverage() for model in CONFIG_ORDER}

    for run in runs:
        row, detail = inventory_one(run, base)
        manifest_rows.append(row)
        bucket = per_config[run.configuration]
        outcome = "pass" if run.final_pass else "fail"
        bucket["assigned"] += 1
        bucket[f"assigned_{outcome}"] += 1
        for key in (
            "events_available",
            "call_usage_available",
            "final_eval_available",
            "initial_state_available",
            "final_artifact_available",
        ):
            if row[key]:
                bucket[key] += 1
                bucket[f"{key}_{outcome}"] += 1
        if row["identity_status"] != "ok":
            bucket["identity_not_ok"] += 1
            unresolved.append(
                {
                    "run_id": run.run_id,
                    "configuration": run.configuration,
                    "task_id": run.task_id,
                    "reason": row["identity_status"],
                    "notes": detail.get("identity_notes") or "",
                    "stage": "identity",
                }
            )
        event_kinds.update(detail.get("event_kinds") or {})
        tools.update(detail.get("tools") or {})
        mutations.update(detail.get("mutations") or {})
        if detail.get("unresolved"):
            unresolved.extend(detail["unresolved"])

    for model in CONFIG_ORDER:
        bucket = per_config[model]
        for outcome in ("pass", "fail", ""):
            suffix = f"_{outcome}" if outcome else ""
            coverage_rows.append(
                {
                    "configuration": model,
                    "outcome": outcome or "all",
                    "assigned": bucket[f"assigned{suffix}" if outcome else "assigned"],
                    "events_available": bucket[f"events_available{suffix}" if outcome else "events_available"],
                    "call_usage_available": bucket[f"call_usage_available{suffix}" if outcome else "call_usage_available"],
                    "final_eval_available": bucket[f"final_eval_available{suffix}" if outcome else "final_eval_available"],
                    "initial_state_available": bucket[f"initial_state_available{suffix}" if outcome else "initial_state_available"],
                    "final_artifact_available": bucket[f"final_artifact_available{suffix}" if outcome else "final_artifact_available"],
                    "identity_not_ok": bucket["identity_not_ok"] if not outcome else "",
                }
            )

    write_csv(output_dir / "run_manifest.csv", manifest_rows, RUN_MANIFEST_FIELDS)
    write_csv(
        output_dir / "coverage.csv",
        coverage_rows,
        (
            "configuration",
            "outcome",
            "assigned",
            "events_available",
            "call_usage_available",
            "final_eval_available",
            "initial_state_available",
            "final_artifact_available",
            "identity_not_ok",
        ),
    )
    write_csv(
        output_dir / "unresolved.csv",
        unresolved,
        ("run_id", "configuration", "task_id", "reason", "notes", "stage"),
    )
    write_json(
        output_dir / "event_type_counts.json",
        {"event_kinds": dict(event_kinds), "tools": dict(tools), "mutations": dict(mutations)},
    )
    write_json(output_dir / "environment.json", env)
    write_json(
        output_dir / "official_pass_counts.json",
        official_pass_counts(runs),
    )
    summary = {
        "n_runs": len(manifest_rows),
        "official_pass_counts": official_pass_counts(runs),
        "environment": env,
        "output_dir": str(output_dir),
    }
    write_json(output_dir / "inventory_summary.json", summary)
    (output_dir / "README.md").write_text(
        _inventory_readme(summary, env),
        encoding="utf-8",
    )
    return summary


def inventory_one(run: OfficialRun, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    mapped = Path(run.mapped_run_dir)
    identity = inspect_identity(run)
    events_path = mapped / "agent" / "openhands_events.jsonl"
    persistence = mapped / "agent" / "openhands_persistence"
    events = []
    event_source = ""
    if events_path.is_file() and events_path.stat().st_size > 0:
        events = load_events(events_path)
        event_source = "openhands_events.jsonl"
    elif persistence.is_dir():
        events = load_persistence_events(persistence)
        event_source = "openhands_persistence"
    completions, pair_stats = pair_completions(events) if events else ([], {})
    audit_path = mapped / "agent" / "context_audit.jsonl"
    usage_path = mapped / "agent" / "usage.json"
    ledger = build_run_ledger(
        configuration=run.configuration,
        audit_path=audit_path,
        usage_path=usage_path,
        events=events,
    )
    eval_result = mapped / "eval" / "result.json"
    submission = mapped / "submission"
    task_dir = root / "benchmark" / "tasks" / run.task_id
    initial = initial_state_available(root, run.task_id, task_dir)
    mutations = Counter(item.mutation_kind for item in completions)
    unresolved = []
    if not events:
        unresolved.append(
            {
                "run_id": run.run_id,
                "configuration": run.configuration,
                "task_id": run.task_id,
                "reason": "events_missing",
                "notes": "",
                "stage": "inventory",
            }
        )
    if not eval_result.is_file():
        unresolved.append(
            {
                "run_id": run.run_id,
                "configuration": run.configuration,
                "task_id": run.task_id,
                "reason": "final_eval_missing",
                "notes": "original eval/result.json absent",
                "stage": "inventory",
            }
        )
    row = {
        "run_id": run.run_id,
        "configuration": run.configuration,
        "task_id": run.task_id,
        "suite_id": run.suite_id,
        "source_run_dir": run.source_run_dir,
        "mapped_run_dir": run.mapped_run_dir,
        "final_pass": run.final_pass,
        "lift_type": run.lift_type,
        "identity_status": identity.status,
        "events_available": bool(events),
        "call_usage_available": call_usage_available(ledger),
        "final_eval_available": eval_result.is_file(),
        "initial_state_available": initial["available"],
        "final_artifact_available": submission.is_dir(),
        "path_identity_ok": identity.path_identity_ok,
    }
    detail = {
        "event_kinds": count_event_kinds(events),
        "tools": count_tools(completions),
        "mutations": dict(mutations),
        "pair_stats": pair_stats,
        "event_source": event_source,
        "identity_notes": identity.notes,
        "token_usage_status": ledger.token_usage_status,
        "token_alignment_status": ledger.token_alignment_status,
        "initial_state": initial,
        "unresolved": unresolved,
    }
    return row, detail


def initial_state_available(root: Path, task_id: str, task_dir: Path) -> dict[str, Any]:
    registry_path = root / "benchmark" / "sources" / "registry.json"
    notes = []
    archive_ok = False
    try:
        registry = read_json(registry_path)
        snapshot = None
        for item in registry.get("snapshots", []):
            if task_id in item.get("task_ids", []):
                snapshot = item
                break
        if snapshot is None:
            notes.append("no_source_snapshot")
        else:
            archive = root / str(snapshot.get("archive_path") or "")
            archive_ok = archive.is_file() and snapshot.get("status") == "ready"
            if not archive_ok:
                notes.append("source_archive_missing")
    except (OSError, ValueError):
        notes.append("source_registry_unreadable")
    task_ok = all(
        (task_dir / name).exists()
        for name in ("TASK.md", "metadata.json", "requirements.lock", "public_tests", "hidden_tests")
    )
    return {
        "available": bool(archive_ok and task_ok),
        "archive_ok": archive_ok,
        "task_package_ok": task_ok,
        "notes": "; ".join(notes),
    }


def collect_environment(root: Path) -> dict[str, Any]:
    eval_image = docker_image_identity(PINNED_EVAL_IMAGE)
    replay_image = docker_image_identity(PINNED_REPLAY_IMAGE)
    latest = docker_image_identity("featureliftbench-eval:latest")
    return {
        "git_commit": git_commit(root),
        "git_dirty": git_dirty(root),
        "eval_code_hash": hash_files(root, EVAL_CODE_RELATIVE),
        "eval_image": eval_image,
        "replay_image": replay_image,
        "latest_eval_image": latest,
        "pinned_eval_image": PINNED_EVAL_IMAGE,
        "pinned_replay_image": PINNED_REPLAY_IMAGE,
        "paper_sources_sha256": sha256_file(root / "docs" / "paper" / "paper_sources.json"),
        "membership_sha256": sha256_file(root / "docs" / "paper" / "writing" / "python150_membership.json"),
        "main_results_sha256": sha256_file(
            root / "reports/paper_analysis/python150_prime_v2_analysis_20260905/task_results.csv"
        ),
        "note": (
            "Use the pinned python200-prime-212930ea evaluator tag, never latest. "
            "Local image Id may differ from run.json recorded digest; record both."
        ),
    }


def _empty_coverage() -> dict[str, int]:
    keys = [
        "assigned",
        "assigned_pass",
        "assigned_fail",
        "events_available",
        "events_available_pass",
        "events_available_fail",
        "call_usage_available",
        "call_usage_available_pass",
        "call_usage_available_fail",
        "final_eval_available",
        "final_eval_available_pass",
        "final_eval_available_fail",
        "initial_state_available",
        "initial_state_available_pass",
        "initial_state_available_fail",
        "final_artifact_available",
        "final_artifact_available_pass",
        "final_artifact_available_fail",
        "identity_not_ok",
    ]
    return {key: 0 for key in keys}


def _inventory_readme(summary: dict[str, Any], env: dict[str, Any]) -> str:
    counts = summary["official_pass_counts"]
    lines = [
        "# Token efficiency inventory",
        "",
        f"Official runs: {summary['n_runs']}",
        f"Git commit: {env.get('git_commit')}",
        f"Pinned eval image: {env.get('pinned_eval_image')}",
        f"Eval image id: {(env.get('eval_image') or {}).get('id')}",
        "",
        "Official pass counts (must remain 115/108/102/68/63/36):",
    ]
    for model in CONFIG_ORDER:
        lines.append(f"- {model}: {counts.get(model)}")
    lines.extend(
        [
            "",
            "This inventory is read-only. It does not replay agents or evaluate snapshots.",
            "Do not use featureliftbench-eval:latest.",
        ]
    )
    return "\n".join(lines) + "\n"
