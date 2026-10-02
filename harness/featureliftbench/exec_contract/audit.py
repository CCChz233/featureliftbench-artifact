"""Audit writer for exec_contract runs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .common import AUDIT_FILE


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def evidence_gate_failures(
    *,
    collect_meta: dict[str, Any] | None,
    synthesize_meta: dict[str, Any] | None,
) -> list[str]:
    """Return fail-closed reasons before an implementation agent is called."""

    collect = collect_meta or {}
    synthesize = synthesize_meta or {}
    failures: list[str] = []
    if _as_int(collect.get("collector_returncode"), -1) != 0:
        failures.append("upstream collector did not exit 0")
    if collect.get("pytest_passed") is not True:
        failures.append("selected upstream pytest did not pass")
    if _as_int(collect.get("useful_trace_events")) < 1:
        failures.append("no relevant upstream trace event")
    if str(collect.get("trace_quality") or "low") != "high":
        failures.append("trace quality is not high")
    if not synthesize.get("contracts_substantive", False):
        failures.append("behavior contracts are not substantive")
    if _as_int(
        synthesize.get("behavior_assertions")
        if synthesize.get("behavior_assertions") is not None
        else synthesize.get("scenario_assertions")
        or 0
    ) < 1:
        failures.append("no executable behavioral assertion")
    if not synthesize.get("api_closure_complete", False):
        failures.append("required API closure is incomplete")
    if not synthesize.get("signature_closure_complete", False):
        failures.append("published signature closure is incomplete")
    if _as_int(synthesize.get("clause_bound_obligations")) < 1:
        failures.append("no dynamic observation is bound to a public TASK clause")
    return failures


def compute_evidence_gate_ok(
    *,
    collect_meta: dict[str, Any] | None,
    synthesize_meta: dict[str, Any] | None,
) -> bool:
    return not evidence_gate_failures(
        collect_meta=collect_meta,
        synthesize_meta=synthesize_meta,
    )


def compute_contract_gate_ok(
    *,
    collect_meta: dict[str, Any] | None,
    synthesize_meta: dict[str, Any] | None,
    verify_final: dict[str, Any] | None,
) -> bool:
    """Gate is green only when verify passes AND contracts are substantive.

    Vacuous surface-only suites cannot count as gate ok even if pytest is green.
    Require at least two scenario assertions (behavioral), not hasattr-only.
    """

    if not (verify_final or {}).get("ok"):
        return False
    syn = synthesize_meta or {}
    if syn.get("contract_variant") == "fcec" and not compute_evidence_gate_ok(
        collect_meta=collect_meta,
        synthesize_meta=synthesize_meta,
    ):
        return False
    if not syn.get("contracts_substantive", False):
        return False
    if (
        syn.get("contract_variant") in {"cgcc_lite", "cgcc_roc", "cgcc_rmc"}
        and not syn.get("mutation_adequacy_ok", False)
    ):
        return False
    scen = _as_int(
        syn.get("behavior_assertions")
        if syn.get("contract_variant") == "fcec"
        else syn.get("scenario_assertions")
        or 0
    )
    minimum_assertions = 1 if syn.get("contract_variant") == "fcec" else 2
    if scen < minimum_assertions:
        return False
    # Reject verify "green" that is mostly skips (hasattr noise / doc skips).
    stdout = str((verify_final or {}).get("stdout_tail") or "")
    m = re.search(r"(\d+)\s+passed.*?(\d+)\s+skipped", stdout)
    if m:
        passed_n, skipped_n = int(m.group(1)), int(m.group(2))
        if passed_n > 0 and skipped_n >= passed_n:
            return False
    return True


def write_exec_contract_audit(
    output_dir: str | Path,
    *,
    variant: str = "clean3",
    collect_meta: dict[str, Any] | None,
    synthesize_meta: dict[str, Any] | None,
    verify_initial: dict[str, Any] | None,
    verify_final: dict[str, Any] | None,
    repair_rounds_used: int,
    agent_primary: dict[str, Any] | None = None,
    agent_repair: dict[str, Any] | None = None,
    fallback_to_main: bool = False,
) -> Path:
    path = Path(output_dir).resolve() / AUDIT_FILE
    gate_ok = compute_contract_gate_ok(
        collect_meta=collect_meta,
        synthesize_meta=synthesize_meta,
        verify_final=verify_final,
    )
    payload = {
        "schema_version": "featureliftbench.exec_contract_phase.v3",
        "protocol": (
            variant
            if variant in {"cgcc_lite", "cgcc_roc", "cgcc_rmc"}
            else "exec_contract"
        ),
        "contract_variant": variant,
        "phase0": {
            "collect": collect_meta or {},
            "synthesize": synthesize_meta or {},
            "evidence_gate_ok": compute_evidence_gate_ok(
                collect_meta=collect_meta,
                synthesize_meta=synthesize_meta,
            ),
            "evidence_gate_failures": evidence_gate_failures(
                collect_meta=collect_meta,
                synthesize_meta=synthesize_meta,
            ),
        },
        "phase1": {
            "agent": _compact(agent_primary),
            "mode": "main_fallback" if fallback_to_main else "execution_contract",
        },
        "phase2": {
            "verify_initial": verify_initial or {},
            "verify_final": verify_final or {},
            "repair_rounds_used": repair_rounds_used,
            "contract_gate_ok": gate_ok,
            "contracts_substantive": bool((synthesize_meta or {}).get("contracts_substantive")),
            "agent_repair": _compact(agent_repair),
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
