"""Frozen controller and descriptive analysis for the OpenHands RSG Pilot."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from ..agent_adapters import AgentRunConfig
from ..agent_config import load_agent_run_config
from ..closure_gold import load_closure_gold, score_closure
from ..freeze import file_manifest, manifest_digest
from ..suite_utils import run_failure_class
from ..trajectory_audit import audit_trajectory, read_event_jsonl
from .hashing import digest_json
from .runtime import prewarm_repo_graph


@dataclass(frozen=True)
class PilotCell:
    order: int
    task_id: str
    arm: str
    replicate: int
    profile: str

    @property
    def cell_id(self) -> str:
        short_task = self.task_id.split("__", 1)[0]
        return f"{self.order:03d}_{short_task}_{self.arm}_r{self.replicate}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "cell_id": self.cell_id,
            "task_id": self.task_id,
            "arm": self.arm,
            "replicate": self.replicate,
            "profile": self.profile,
        }


def load_pilot_spec(path: str | Path) -> dict[str, Any]:
    spec_path = Path(path)
    value = tomllib.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("pilot spec must be a TOML table")
    validate_pilot_spec(value)
    return value


def validate_pilot_spec(spec: dict[str, Any]) -> None:
    tasks = spec.get("tasks")
    arms = spec.get("arms")
    context = spec.get("context")
    if not isinstance(tasks, list) or len(tasks) != 2 or not all(isinstance(item, str) for item in tasks):
        raise ValueError("pilot spec must freeze exactly two task IDs")
    if not isinstance(arms, dict) or set(arms) != {"p0", "p3"}:
        raise ValueError("pilot spec must define exactly p0 and p3 arms")
    if not isinstance(context, dict):
        raise ValueError("pilot context table is required")
    trigger = int(context.get("window_tokens", 0)) - int(context.get("reserved_output_tokens", 0))
    if trigger != int(context.get("trigger_tokens", -1)):
        raise ValueError("pilot context trigger does not match window minus output reserve")
    if trigger // 2 != int(context.get("target_tokens", -1)):
        raise ValueError("pilot context target must be half of the trigger")
    repeats = int(spec.get("repeats", 0))
    if repeats != 3:
        raise ValueError("rsg pilot v1 requires exactly three replicates")
    expected = len(tasks) * len(arms) * repeats
    planned = int((spec.get("acceptance") or {}).get("planned_cells", 0))
    if expected != planned:
        raise ValueError("planned_cells does not match tasks × arms × repeats")


def build_execution_order(spec: dict[str, Any]) -> list[PilotCell]:
    tasks = [str(value) for value in spec["tasks"]]
    profiles = {arm: str(spec["arms"][arm]["profile"]) for arm in ("p0", "p3")}
    first_task = tasks[0]
    ordered = [
        (first_task, "p0", 1),
        (first_task, "p3", 1),
    ]
    remaining = [
        (task_id, arm, replicate)
        for task_id in tasks
        for arm in ("p0", "p3")
        for replicate in range(1, int(spec["repeats"]) + 1)
        if (task_id, arm, replicate) not in ordered
    ]
    random.Random(int(spec["order_seed"])).shuffle(remaining)
    ordered.extend(remaining)
    return [
        PilotCell(index, task_id, arm, replicate, profiles[arm])
        for index, (task_id, arm, replicate) in enumerate(ordered, start=1)
    ]


def validate_arm_profiles(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    config_path = root / str(spec["agent_config"])
    summaries: dict[str, dict[str, Any]] = {}
    envs: dict[str, dict[str, str]] = {}
    for arm in ("p0", "p3"):
        profile = str(spec["arms"][arm]["profile"])
        loaded = load_agent_run_config(
            base_config=AgentRunConfig(agent=str(spec["agent"])),
            config_path=config_path,
            profile_name=profile,
            env_file=root / ".env",
        )
        summaries[arm] = loaded.summary
        envs[arm] = dict(loaded.run_config.env or {})

    ignored_summary = {
        "profile",
        "repo_graph_mode",
        "repo_graph_transport",
        "repo_graph_fail_fast",
        "repo_graph_bootstrap_max_nodes",
        "repo_graph_bootstrap_max_chars",
        "repo_graph_query_max_chars",
    }
    p0_common = {key: value for key, value in summaries["p0"].items() if key not in ignored_summary}
    p3_common = {key: value for key, value in summaries["p3"].items() if key not in ignored_summary}
    if p0_common != p3_common:
        raise ValueError("P0/P3 profiles differ outside repository graph fields")
    if summaries["p0"]["repo_graph_mode"] != "disabled":
        raise ValueError("P0 must keep repository graph disabled")
    if summaries["p3"]["repo_graph_mode"] != "closure":
        raise ValueError("P3 must use repository graph closure mode")
    expected_context = spec["context"]
    for arm in ("p0", "p3"):
        summary = summaries[arm]
        checks = {
            "context_window_tokens": expected_context["window_tokens"],
            "reserved_output_tokens": expected_context["reserved_output_tokens"],
            "openhands_condenser_trigger_tokens": expected_context["trigger_tokens"],
            "openhands_condenser_target_tokens": expected_context["target_tokens"],
            "openhands_condenser_keep_first": expected_context["keep_first"],
            "openhands_condenser_max_events": expected_context["max_events"],
            "openhands_max_steps": 120,
            "native_tool_calling": "true",
        }
        for key, expected in checks.items():
            if summary.get(key) != expected:
                raise ValueError(f"{arm} profile has wrong {key}: {summary.get(key)!r}")
    return {
        "summaries": summaries,
        "profile_digest": digest_json(summaries),
        "secrets_present": any(
            key.upper().endswith(("API_KEY", "TOKEN", "SECRET", "PASSWORD"))
            for values in envs.values()
            for key in values
        ),
    }


def freeze_experiment(
    spec: dict[str, Any],
    *,
    spec_path: Path,
    experiment_dir: Path,
    root: Path,
) -> dict[str, Any]:
    profile_validation = validate_arm_profiles(spec, root=root)
    task_paths = [root / str(spec["task_root"]) / str(task_id) for task_id in spec["tasks"]]
    for task_path in task_paths:
        if not (task_path / "metadata.json").is_file():
            raise ValueError(f"pilot task is missing: {task_path.name}")
    code_paths = [
        root / "harness" / "featureliftbench" / "repo_graph",
        root / "harness" / "featureliftbench" / "agent_config.py",
        root / "harness" / "featureliftbench" / "agent_runner.py",
        root / "harness" / "featureliftbench" / "openhands_runner.py",
        root / "harness" / "featureliftbench" / "trajectory_audit.py",
        root / "harness" / "config" / "agents.example.toml",
        root / "harness" / "config" / "repo_graph_requirements.lock",
        root / "docker" / "Dockerfile.agent",
        spec_path,
    ]
    manifest: dict[str, Any] = {
        "schema_version": "featureliftbench.rsg_pilot.freeze.v1",
        "generated_at": _utc_now(),
        "spec": spec,
        "spec_digest": digest_json(spec),
        "profile_digest": profile_validation["profile_digest"],
        "profile_summaries": profile_validation["summaries"],
        "task_file_manifest": file_manifest(task_paths, root=root),
        "code_file_manifest": file_manifest(code_paths, root=root),
        "execution_order": [cell.to_dict() for cell in build_execution_order(spec)],
        "images": {
            "agent": inspect_docker_image(str(spec["agent_image"])),
            "evaluator": inspect_docker_image(str(spec["eval_image"])),
        },
        "agent_runtime": inspect_agent_runtime(str(spec["agent_image"])),
        "api_determinism": {
            "request_seed": None,
            "request_temperature": None,
            "documented_provider_default_temperature": 1.0,
            "replicate_id_recorded": True,
            "order_seed": int(spec["order_seed"]),
            "server_side_determinism_claimed": False,
        },
    }
    manifest["freeze_id"] = manifest_digest(manifest)
    _write_json(experiment_dir / "experiment_manifest.json", manifest)
    return manifest


def inspect_docker_image(image: str) -> dict[str, Any]:
    process = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError(f"required Docker image is unavailable: {image}")
    payload = json.loads(process.stdout)
    detail = payload[0] if isinstance(payload, list) and payload else {}
    return {
        "tag": image,
        "id": detail.get("Id"),
        "repo_digests": detail.get("RepoDigests") or [],
        "os": detail.get("Os"),
        "architecture": detail.get("Architecture"),
    }


def inspect_agent_runtime(image: str) -> dict[str, Any]:
    system = _docker_python_metadata(image, "python")
    openhands = _docker_python_metadata(image, "/opt/uv-tools/openhands/bin/python")
    packages = {
        str(item["name"]).lower().replace("_", "-"): str(item["version"])
        for item in openhands.get("packages", [])
        if isinstance(item, dict)
    }
    openhands_version = packages.get("openhands") or packages.get("openhands-ai")
    sdk_version = packages.get("openhands-sdk")
    if not str(system.get("python", "")).startswith("3.12"):
        raise ValueError(f"pilot agent image must use Python 3.12, got {system.get('python')}")
    if openhands_version != "1.16.0" or sdk_version != "1.21.0":
        raise ValueError(
            "pilot agent image has wrong OpenHands runtime: "
            f"OpenHands={openhands_version}, SDK={sdk_version}"
        )
    expected_parsers = {
        "tree-sitter": "0.26.0",
        "tree-sitter-python": "0.25.0",
        "tree-sitter-go": "0.25.0",
    }
    system_packages = {
        str(item["name"]).lower().replace("_", "-"): str(item["version"])
        for item in system.get("packages", [])
        if isinstance(item, dict)
    }
    for package, expected in expected_parsers.items():
        if system_packages.get(package) != expected:
            raise ValueError(
                f"pilot agent image has wrong {package}: {system_packages.get(package)!r}"
            )
    cli = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "flb-rsg", image, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    if cli.returncode != 0:
        raise ValueError("pilot agent image does not provide a working flb-rsg CLI")
    return {"system": system, "openhands_environment": openhands, "flb_rsg_cli": True}


def _docker_python_metadata(image: str, executable: str) -> dict[str, Any]:
    code = (
        "import importlib.metadata as m,json,platform;"
        "names=('openhands','openhands-ai','openhands-sdk','tree-sitter','tree-sitter-python','tree-sitter-go');"
        "items=[];"
        "[(items.append({'name':n,'version':m.version(n)})) for n in names if _has(n,m)];"
        "print(json.dumps({'python':platform.python_version(),'packages':items},sort_keys=True))"
    )
    # Keep the one-liner compatible with both the system and uv-tool Python.
    code = code.replace("if _has(n,m)", "if any(d.metadata.get('Name','').lower()==n for d in m.distributions())")
    process = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", executable, image, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError(f"cannot inspect Python runtime in {image}: {executable}")
    value = json.loads(process.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"invalid Python runtime metadata from {image}: {executable}")
    return value


def prewarm_graphs(spec: dict[str, Any], *, experiment_dir: Path, root: Path) -> dict[str, Any]:
    cache_root = experiment_dir / "graph_cache"
    records: dict[str, Any] = {}
    for task_id in spec["tasks"]:
        records[str(task_id)] = prewarm_repo_graph(
            root / str(spec["task_root"]) / str(task_id) / "repo",
            cache_root,
        )
    _write_json(experiment_dir / "graph_prewarm.json", records)
    manifest_path = experiment_dir / "experiment_manifest.json"
    if manifest_path.is_file():
        manifest = _read_json(manifest_path)
        manifest["graph_snapshots"] = {
            task_id: {
                "snapshot_id": value.get("snapshot_id"),
                "graph_hash": value.get("graph_hash"),
            }
            for task_id, value in records.items()
        }
        manifest["freeze_id"] = manifest_digest(manifest)
        _write_json(manifest_path, manifest)
    return records


def run_pilot(
    spec: dict[str, Any],
    *,
    experiment_dir: Path,
    root: Path,
    execute: bool,
) -> dict[str, Any]:
    cells = build_execution_order(spec)
    state = _load_state(experiment_dir, cells)
    if not execute:
        _write_json(experiment_dir / "pilot_state.json", state)
        return state

    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    environment = {
        "FEATURELIFTBENCH_REPO_GRAPH_CACHE_DIR": str((experiment_dir / "graph_cache").resolve()),
        "PYTHONPATH": str(root / "harness")
        + (os.pathsep + existing_pythonpath if existing_pythonpath else ""),
    }
    consecutive_infra = int(state.get("consecutive_infrastructure_failures", 0))
    for cell in cells:
        if cell.cell_id in state["completed_cell_ids"]:
            continue
        cell_dir = experiment_dir / "cells" / cell.cell_id
        cell_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {}
        selected_attempt_dir = cell_dir
        controller_attempts: list[dict[str, Any]] = []
        max_attempts = int(spec.get("max_infrastructure_attempts", 2))
        for controller_attempt in range(1, max_attempts + 1):
            attempt_dir = cell_dir / "attempts" / f"attempt_{controller_attempt:02d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            command = pilot_cell_command(spec, cell, cell_dir=attempt_dir, root=root)
            try:
                process = subprocess.run(
                    command,
                    cwd=root,
                    env={**os.environ, **environment},
                    check=False,
                )
            except KeyboardInterrupt:
                controller_attempts.append(
                    {
                        "attempt": controller_attempt,
                        "output_dir": str(attempt_dir),
                        "returncode": None,
                        "infrastructure_failure": None,
                        "failure_class": "controller_interrupted",
                    }
                )
                _write_json(cell_dir / "controller_attempts.json", {"attempts": controller_attempts})
                state["status"] = "stopped"
                state["stop_reason"] = "controller_interrupted"
                state["interrupted_cell_id"] = cell.cell_id
                _write_json(experiment_dir / "pilot_state.json", state)
                raise
            result = load_cell_result(attempt_dir, cell.task_id)
            attempt_record = classify_controller_attempt(process.returncode, result)
            attempt_record.update(
                {
                    "attempt": controller_attempt,
                    "output_dir": str(attempt_dir),
                    "run_json": str(attempt_dir / cell.task_id / "run.json"),
                }
            )
            controller_attempts.append(attempt_record)
            _write_json(cell_dir / "controller_attempts.json", {"attempts": controller_attempts})
            selected_attempt_dir = attempt_dir
            if not attempt_record["infrastructure_failure"] or controller_attempt >= max_attempts:
                break

        record = cell_result_record(cell, result, cell_dir=selected_attempt_dir)
        record["controller_attempt"] = len(controller_attempts)
        record["controller_attempts_json"] = str(cell_dir / "controller_attempts.json")
        state["results"].append(record)
        state["completed_cell_ids"].append(cell.cell_id)
        if record["infrastructure_failure"]:
            consecutive_infra += 1
        else:
            consecutive_infra = 0
        state["consecutive_infrastructure_failures"] = consecutive_infra
        state["observed_total_tokens"] = sum(int(item.get("total_tokens") or 0) for item in state["results"])
        stop_reason = stopping_reason(spec, state)
        state["status"] = "stopped" if stop_reason else "running"
        state["stop_reason"] = stop_reason or ""
        _write_json(experiment_dir / "pilot_state.json", state)
        if stop_reason:
            break

    if len(state["completed_cell_ids"]) == len(cells):
        state["status"] = "complete"
        state["stop_reason"] = ""
    state["analysis"] = analyze_pilot_results(state["results"])
    _write_json(experiment_dir / "pilot_state.json", state)
    _write_json(experiment_dir / "pilot_analysis.json", state["analysis"])
    return state


def pilot_cell_command(
    spec: dict[str, Any], cell: PilotCell, *, cell_dir: Path, root: Path
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "featureliftbench.cli",
        "run-agent",
        str(spec["task_root"]),
        "--agent",
        str(spec["agent"]),
        "--agent-config",
        str(spec["agent_config"]),
        "--agent-profile",
        cell.profile,
        "--env-file",
        ".env",
        "--task-id",
        cell.task_id,
        "--output",
        str(cell_dir),
        "--timeout-seconds",
        str(spec["timeout_seconds"]),
        "--num-workers",
        "1",
        "--retry-rate-limit",
        str(spec["retry_rate_limit"]),
        "--agent-docker",
        "--agent-docker-image",
        str(spec["agent_image"]),
        "--eval-docker",
        "--eval-docker-image",
        str(spec["eval_image"]),
        "--no-progress",
    ]


def load_cell_result(cell_dir: Path, task_id: str) -> dict[str, Any]:
    path = cell_dir / task_id / "run.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def is_infrastructure_failure(run: dict[str, Any]) -> bool:
    if not run:
        return True
    if run_failure_class(run) in {"agent_setup_failed", "rate_limited", "eval_infra_failed"}:
        return True
    text = json.dumps({"errors": run.get("errors"), "agent": run.get("agent")}, ensure_ascii=False).lower()
    return any(
        marker in text
        for marker in (
            "apiconnectionerror",
            "connecterror",
            "connection reset",
            "connection refused",
            "network is unreachable",
            "temporary failure in name resolution",
            "server disconnected",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
            "docker daemon",
        )
    )


def classify_controller_attempt(returncode: int, run: dict[str, Any]) -> dict[str, Any]:
    """Classify retries from the structured run result, not CLI exit semantics.

    ``run-agent`` exits non-zero for ordinary model/task failures. Treating every
    non-zero exit as infrastructure would silently add paid replicates and
    contaminate the frozen design. A missing or infrastructure-class run remains
    retryable; a complete logical failure does not.
    """

    failure_class = run_failure_class(run) if run else "missing_run"
    return {
        "returncode": returncode,
        "cli_nonzero": returncode != 0,
        "infrastructure_failure": is_infrastructure_failure(run),
        "failure_class": failure_class,
    }


def cell_result_record(cell: PilotCell, run: dict[str, Any], *, cell_dir: Path) -> dict[str, Any]:
    agent = run.get("agent") if isinstance(run.get("agent"), dict) else {}
    usage = agent.get("usage") if isinstance(agent.get("usage"), dict) else {}
    context = usage.get("context_audit") if isinstance(usage.get("context_audit"), dict) else {}
    graph = run.get("repo_graph") if isinstance(run.get("repo_graph"), dict) else {}
    evaluation = run.get("evaluation") if isinstance(run.get("evaluation"), dict) else {}
    scores = evaluation.get("scores") if isinstance(evaluation.get("scores"), dict) else {}
    eval_result_path = cell_dir / cell.task_id / "eval" / "result.json"
    eval_result = _read_json(eval_result_path) if eval_result_path.is_file() else {}
    build_path = cell_dir / cell.task_id / "agent" / "repo_graph_build.json"
    graph_build = _read_json(build_path) if build_path.is_file() else {}
    trajectory_path = cell_dir / cell.task_id / "agent" / "openhands_events.jsonl"
    trajectory = audit_trajectory(read_event_jsonl(trajectory_path))
    closure_path = cell_dir / cell.task_id / "agent" / "state" / "repo_graph" / "closure_overlay.json"
    return {
        **cell.to_dict(),
        "run_json": str(cell_dir / cell.task_id / "run.json"),
        "status": run.get("status", "missing"),
        "failure_class": run_failure_class(run) if run else "missing_run",
        "infrastructure_failure": is_infrastructure_failure(run),
        "formal_pass": run.get("status") == "passed",
        "public_pass": _gate_pass(eval_result, "public_tests"),
        "hidden_pass": _gate_pass(eval_result, "hidden_tests"),
        "install_pass": _gate_pass(eval_result, "submission_install"),
        "extraction_ratio": scores.get("extraction_ratio"),
        "final_score": scores.get("final_score"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "max_prompt_tokens_per_call": context.get("max_prompt_tokens_per_call"),
        "condensation_events": context.get("condensation_events"),
        "forgotten_event_count": context.get("forgotten_event_count"),
        "context_violation": context.get("context_violation") is True,
        "repo_graph": graph,
        "graph_initialized": bool(graph_build) and graph_build.get("status") != "failed",
        "graph_cache_hit": (graph_build.get("cache") or {}).get("hit")
        if isinstance(graph_build.get("cache"), dict)
        else None,
        "graph_warm_load_seconds": graph_build.get("duration_seconds"),
        "graph_rss_peak_bytes": graph_build.get("rss_peak_bytes"),
        "graph_bytes": graph_build.get("graph_bytes"),
        "closure_gold_file_score": _closure_gold_file_score(
            root=Path(__file__).resolve().parents[3],
            task_id=cell.task_id,
            closure_path=closure_path,
        ),
        "trajectory_audit": trajectory,
        "system_fingerprints": trajectory.get("system_fingerprints", []),
        "graph_leakage": _graph_leakage(graph_build),
        "protocol_violation": graph.get("protocol_violation") is True,
        "adoption_compliant": graph.get("adoption_compliant") is True,
    }


def stopping_reason(spec: dict[str, Any], state: dict[str, Any]) -> str | None:
    results = state.get("results", [])
    current = results[-1] if results else {}
    if current.get("arm") == "p3":
        if not current.get("graph_initialized"):
            return "graph_initialization_failure"
        if current.get("graph_leakage"):
            return "graph_input_leakage"
        if current.get("protocol_violation"):
            return "repo_graph_protocol_violation"
    if current.get("context_violation"):
        return "context_violation"
    if len(results) == 2:
        if any(item.get("infrastructure_failure") for item in results):
            return "paid_pair_infrastructure_gate_failed"
        p3 = next((item for item in results if item.get("arm") == "p3"), {})
        if not p3.get("adoption_compliant"):
            return "paid_pair_rsg_adoption_gate_failed"
    stops = spec["stopping"]
    if int(state.get("consecutive_infrastructure_failures", 0)) >= int(
        stops["consecutive_infrastructure_failures"]
    ):
        return "consecutive_infrastructure_failures"
    p3_results = [item for item in results if item.get("arm") == "p3"]
    if len(p3_results) == int(stops["adoption_first_n"]):
        adopted = sum(item.get("adoption_compliant") is True for item in p3_results)
        if adopted < int(stops["adoption_minimum"]):
            return "rsg_adoption_below_75_percent"
    if int(state.get("observed_total_tokens", 0)) >= int(stops["max_total_tokens"]):
        return "total_token_cap_reached"
    return None


def analyze_pilot_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    for arm in ("p0", "p3"):
        rows = [row for row in results if row.get("arm") == arm]
        tokens = [int(row["total_tokens"]) for row in rows if isinstance(row.get("total_tokens"), int)]
        by_arm[arm] = {
            "runs": len(rows),
            "formal_passes": sum(row.get("formal_pass") is True for row in rows),
            "raw_total_tokens": tokens,
            "median_total_tokens": median(tokens) if tokens else None,
            "total_token_range": [min(tokens), max(tokens)] if tokens else None,
            "adoption_compliant_runs": sum(row.get("adoption_compliant") is True for row in rows),
            "metrics": {
                key: _descriptive_metric(rows, key)
                for key in (
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "max_prompt_tokens_per_call",
                    "condensation_events",
                    "forgotten_event_count",
                    "extraction_ratio",
                    "final_score",
                    "graph_warm_load_seconds",
                    "graph_rss_peak_bytes",
                    "graph_bytes",
                )
            },
            "trajectory_metrics": {
                key: _descriptive_nested_metric(rows, "trajectory_audit", key)
                for key in (
                    "source_read_count",
                    "unchanged_repeated_reads",
                    "exact_repeated_terminal_commands",
                    "runtime_probe_count",
                )
            },
            "fresh_final_verification_runs": sum(
                (row.get("trajectory_audit") or {}).get("fresh_final_verification") is True
                for row in rows
                if isinstance(row.get("trajectory_audit"), dict)
            ),
        }
    paired: list[dict[str, Any]] = []
    index = {(row.get("task_id"), row.get("replicate"), row.get("arm")): row for row in results}
    for task_id, replicate in sorted(
        {(row.get("task_id"), row.get("replicate")) for row in results},
        key=lambda value: (str(value[0]), int(value[1] or 0)),
    ):
        p0 = index.get((task_id, replicate, "p0"))
        p3 = index.get((task_id, replicate, "p3"))
        if not p0 or not p3:
            continue
        paired.append(
            {
                "task_id": task_id,
                "replicate": replicate,
                "formal_pass_difference_p3_minus_p0": int(bool(p3.get("formal_pass")))
                - int(bool(p0.get("formal_pass"))),
                "total_token_difference_p3_minus_p0": _numeric_difference(
                    p3.get("total_tokens"), p0.get("total_tokens")
                ),
                "max_prompt_difference_p3_minus_p0": _numeric_difference(
                    p3.get("max_prompt_tokens_per_call"), p0.get("max_prompt_tokens_per_call")
                ),
                "repeated_read_difference_p3_minus_p0": _numeric_difference(
                    (p3.get("trajectory_audit") or {}).get("unchanged_repeated_reads"),
                    (p0.get("trajectory_audit") or {}).get("unchanged_repeated_reads"),
                ),
                "runtime_probe_difference_p3_minus_p0": _numeric_difference(
                    (p3.get("trajectory_audit") or {}).get("runtime_probe_count"),
                    (p0.get("trajectory_audit") or {}).get("runtime_probe_count"),
                ),
                "final_score_difference_p3_minus_p0": _numeric_difference(
                    p3.get("final_score"), p0.get("final_score")
                ),
            }
        )
    p0_passes = int(by_arm["p0"]["formal_passes"])
    p3_passes = int(by_arm["p3"]["formal_passes"])
    p0_median = by_arm["p0"]["median_total_tokens"]
    p3_median = by_arm["p3"]["median_total_tokens"]
    acceptance = {
        "formal_correctness_regression_within_one": p3_passes >= p0_passes - 1,
        "rsg_adoption_at_least_five_of_six": by_arm["p3"]["adoption_compliant_runs"] >= 5,
        "token_guard_when_no_pass_gain": (
            True
            if p3_passes > p0_passes or p0_median in {None, 0} or p3_median is None
            else float(p3_median) <= float(p0_median) * 1.2
        ),
    }
    return {
        "reporting_scope": "descriptive_only_no_significance_or_causal_claim",
        "by_arm": by_arm,
        "paired_differences": paired,
        "acceptance": acceptance,
    }


def _load_state(experiment_dir: Path, cells: list[PilotCell]) -> dict[str, Any]:
    path = experiment_dir / "pilot_state.json"
    if path.is_file():
        value = _read_json(path)
        if value.get("planned_cell_ids") != [cell.cell_id for cell in cells]:
            raise ValueError("existing pilot state does not match frozen execution order")
        return value
    return {
        "schema_version": "featureliftbench.rsg_pilot.state.v1",
        "status": "planned",
        "planned_cell_ids": [cell.cell_id for cell in cells],
        "completed_cell_ids": [],
        "results": [],
        "observed_total_tokens": 0,
        "consecutive_infrastructure_failures": 0,
        "stop_reason": "",
    }


def _graph_leakage(build: dict[str, Any]) -> bool:
    scope = build.get("input_scope") if isinstance(build.get("input_scope"), dict) else {}
    return any(int(scope.get(key, 0) or 0) != 0 for key in (
        "hidden_test_inputs",
        "evaluation_inputs",
        "reference_solution_inputs",
    ))


def _gate_pass(evaluation: dict[str, Any], key: str) -> bool | None:
    value = evaluation.get(key)
    return value.get("passed") if isinstance(value, dict) and isinstance(value.get("passed"), bool) else None


def _numeric_difference(left: Any, right: Any) -> int | float | None:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left - right
    return None


def _descriptive_metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [
        row[key]
        for row in rows
        if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)
    ]
    return {
        "raw": values,
        "median": median(values) if values else None,
        "range": [min(values), max(values)] if values else None,
    }


def _descriptive_nested_metric(
    rows: list[dict[str, Any]], parent: str, key: str
) -> dict[str, Any]:
    flattened = [
        {key: nested.get(key)}
        for row in rows
        if isinstance((nested := row.get(parent)), dict)
    ]
    return _descriptive_metric(flattened, key)


def _closure_gold_file_score(
    *, root: Path, task_id: str, closure_path: Path
) -> dict[str, Any] | None:
    task_dir = root / "benchmark" / "tasks" / task_id
    if not task_dir.is_dir() or not closure_path.is_file():
        return None
    closure = _read_json(closure_path)
    predictions: list[str] = []
    for node in closure.get("candidate_nodes", []):
        if not isinstance(node, dict) or not isinstance(node.get("location"), str):
            continue
        path = node["location"].rsplit(":", 1)[0]
        predictions.append(path if path.startswith("repo/") else f"repo/{path}")
    score = score_closure(load_closure_gold(task_dir), predictions, kind="file")
    return score.as_dict() if score is not None else None


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
