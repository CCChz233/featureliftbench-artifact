"""Run artifacts and frozen implementation identity for closure-gate experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .common import AUDIT_FILE
from .common import AUDIT_SCHEMA
from .common import FINAL_RESULT_FILE
from .common import INITIAL_RESULT_FILE


def compute_method_freeze() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    files: dict[str, str] = {}
    tree = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[rel] = digest
        tree.update(rel.encode("utf-8"))
        tree.update(b"\0")
        tree.update(bytes.fromhex(digest))
    return {
        "schema_version": "featureliftbench.contract_closure_method_freeze.v1",
        "package_tree_sha256": tree.hexdigest(),
        "package_files": files,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _aggregate_usage(
    named_agents: list[tuple[str, dict[str, Any] | None]],
) -> dict[str, Any]:
    """Account for every model phase without replacing per-phase evidence."""

    metric_names = (
        "api_calls",
        "assistant_steps",
        "total_messages",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "effective_uncached_prompt_tokens",
        "tool_alias_normalizations",
        "trace_tokens",
        "billed_tokens",
    )
    totals: dict[str, Any] = {name: 0 for name in metric_names}
    phases: list[dict[str, Any]] = []
    for phase_name, agent in named_agents:
        if not isinstance(agent, dict) or not agent:
            continue
        usage = agent.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        phase = {
            "phase": phase_name,
            "duration_seconds": agent.get("duration_seconds", 0.0),
            "passed": agent.get("passed", False),
        }
        cache_available = usage.get("prompt_cache_accounting_available")
        if isinstance(cache_available, bool):
            phase["prompt_cache_accounting_available"] = cache_available
        for name in metric_names:
            value = usage.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[name] += value
                phase[name] = value
        phases.append(phase)
    totals["available"] = bool(phases)
    totals["prompt_cache_accounting_available"] = any(
        phase.get("prompt_cache_accounting_available") is True for phase in phases
    )
    totals["duration_seconds"] = sum(
        float(phase.get("duration_seconds") or 0.0) for phase in phases
    )
    cache_total = totals["prompt_cache_hit_tokens"] + totals["prompt_cache_miss_tokens"]
    totals["prompt_cache_hit_rate"] = (
        totals["prompt_cache_hit_tokens"] / cache_total if cache_total > 0 else None
    )
    totals["phases"] = phases
    context_audits = []
    for _, agent in named_agents:
        if not isinstance(agent, dict):
            continue
        usage = agent.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        audit = usage.get("context_audit")
        if isinstance(audit, dict):
            context_audits.append(audit)
    if context_audits:
        totals["context_audit"] = {
            "available": True,
            "context_violation": any(
                audit.get("context_violation") is True for audit in context_audits
            ),
            "usage_unverified": any(
                audit.get("usage_unverified") is True for audit in context_audits
            ),
            "max_prompt_tokens_per_call": max(
                int(audit.get("max_prompt_tokens_per_call") or 0)
                for audit in context_audits
            ),
            "max_total_tokens_per_call": max(
                int(audit.get("max_total_tokens_per_call") or 0)
                for audit in context_audits
            ),
            "condensation_events": sum(
                int(audit.get("condensation_events") or 0)
                for audit in context_audits
            ),
            "forgotten_event_count": sum(
                int(audit.get("forgotten_event_count") or 0)
                for audit in context_audits
            ),
            "compression_mode": next(
                (
                    str(audit.get("compression_mode"))
                    for audit in context_audits
                    if audit.get("compression_mode")
                ),
                "",
            ),
        }
    return totals


def write_contract_closure_audit(
    output_dir: str | Path,
    *,
    initial: dict[str, Any],
    final: dict[str, Any],
    repair_rounds_used: int,
    agent_primary: dict[str, Any] | None,
    agent_repair: dict[str, Any] | None,
    arm: str = "contract_closure_gate",
    repair_decision: dict[str, Any] | None = None,
    agent_primary_attempts: list[dict[str, Any]] | None = None,
    infrastructure_retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / INITIAL_RESULT_FILE, initial)
    _write_json(output / FINAL_RESULT_FILE, final)
    primary_attempts = [
        attempt for attempt in (agent_primary_attempts or []) if isinstance(attempt, dict)
    ]
    if not primary_attempts and isinstance(agent_primary, dict):
        primary_attempts = [agent_primary]
    named_agents: list[tuple[str, dict[str, Any] | None]] = []
    for index, attempt in enumerate(primary_attempts, start=1):
        phase_name = "primary" if len(primary_attempts) == 1 else f"primary_attempt_{index}"
        named_agents.append((phase_name, attempt))
    named_agents.append(("repair", agent_repair))
    decision = repair_decision or {}
    repair_kind = str(decision.get("repair_kind") or "none")

    payload = {
        "schema_version": AUDIT_SCHEMA,
        "arm": arm,
        "method_freeze": compute_method_freeze(),
        "repair_rounds_used": int(repair_rounds_used),
        "repair_triggered": bool(repair_rounds_used),
        "repair_kind": repair_kind,
        "evidence_completion_rounds_used": (
            int(repair_rounds_used) if repair_kind == "evidence_completion" else 0
        ),
        "defect_repair_rounds_used": (
            int(repair_rounds_used) if repair_kind == "defect_repair" else 0
        ),
        "functional_rescue_candidate": bool(
            repair_rounds_used and repair_kind == "defect_repair"
        ),
        "repair_decision": decision,
        "initial": initial,
        "final": final,
        "agent_primary": agent_primary or {},
        "agent_primary_attempts": primary_attempts,
        "agent_repair": agent_repair or {},
        "infrastructure_retry": infrastructure_retry or {},
        "usage_totals": _aggregate_usage(named_agents),
    }
    _write_json(output / AUDIT_FILE, payload)
    return payload
