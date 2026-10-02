"""Audit writer for self_contract runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import AUDIT_FILE


def write_self_contract_audit(
    output_dir: str | Path,
    *,
    collect_meta: dict[str, Any] | None,
    author_gate: dict[str, Any] | None,
    freeze_meta: dict[str, Any] | None,
    freeze_check: dict[str, Any] | None,
    verify_initial: dict[str, Any] | None,
    verify_final: dict[str, Any] | None,
    author_repair_rounds: int,
    impl_repair_rounds: int,
    agent_author: dict[str, Any] | None = None,
    agent_implement: dict[str, Any] | None = None,
    agent_repair: dict[str, Any] | None = None,
) -> Path:
    path = Path(output_dir).resolve() / AUDIT_FILE
    gate_impl_ok = bool((verify_final or {}).get("ok")) and bool(
        (freeze_check or {}).get("ok", True)
    )
    payload = {
        "schema_version": "featureliftbench.self_contract_phase.v1",
        "protocol": "self_contract",
        "phase0": {"collect": collect_meta or {}},
        "phase_a_author": {
            "gate": author_gate or {},
            "agent": _compact(agent_author),
            "repair_rounds_used": author_repair_rounds,
            "freeze": freeze_meta or {},
        },
        "phase_b_implement": {
            "agent": _compact(agent_implement),
            "verify_initial": verify_initial or {},
            "verify_final": verify_final or {},
            "repair_rounds_used": impl_repair_rounds,
            "freeze_check": freeze_check or {},
            "agent_repair": _compact(agent_repair),
            "contract_gate_ok": gate_impl_ok,
        },
        "gates": {
            "author_ok": bool((author_gate or {}).get("ok")),
            "impl_ok": gate_impl_ok,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _compact(agent: dict[str, Any] | None) -> dict[str, Any] | None:
    if not agent:
        return None
    keep = (
        "name",
        "passed",
        "returncode",
        "duration_seconds",
        "timed_out",
        "reason",
        "resource_limited",
    )
    return {k: agent.get(k) for k in keep}
