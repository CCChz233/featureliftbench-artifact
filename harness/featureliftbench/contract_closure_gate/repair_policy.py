"""Auditable bounded-repair policies for Contract Closure Gate experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import DEFAULT_LITE_MAX_MISSING_APIS
from .common import DEFAULT_LITE_MAX_REPAIR_FAILURES
from .common import LITE_POLICY_VERSION
from .common import LITE_V1_POLICY_VERSION
from .common import LITE_RESCUE_POLICY_VERSION
from .common import LITE_RESCUE_PLUS_POLICY_VERSION
from .common import DEFAULT_RESCUE_PLUS_MAX_REPAIR_CLUSTERS
from .common import V3_POLICY_VERSION

_LOCAL_REPAIR_CATEGORIES = frozenset({"api", "signature", "dependency"})
_V3_REPAIR_CATEGORIES = _LOCAL_REPAIR_CATEGORIES | {"behavior"}
_LITE_RESCUE_PLUS_REPAIR_CATEGORIES = _V3_REPAIR_CATEGORIES | {
    "structure"
}


def _actionable_behavior_failure(item: dict[str, Any]) -> bool:
    if item.get("category") != "behavior" or item.get("status") != "fail":
        return False
    return str(item.get("message") or "").startswith(
        (
            "featurelifted observation differs from stable upstream",
            "featurelifted case failed:",
            "direct assertion failed:",
        )
    )


def _repairable_evidence_failure(item: dict[str, Any]) -> bool:
    if item.get("status") != "fail":
        return False
    if item.get("id") in {"behavior.smoke.required", "behavior.witness.required"}:
        return True
    evidence = item.get("evidence")
    runtime = evidence.get("runtime") if isinstance(evidence, dict) else None
    return (
        item.get("category") == "behavior_evidence"
        and isinstance(runtime, dict)
        and runtime.get("error_kind") == "case_protocol_invalid"
    )


def _actionable_public_witness_failure(item: dict[str, Any]) -> bool:
    if not _actionable_behavior_failure(item):
        return False
    evidence = item.get("evidence")
    return (
        isinstance(evidence, dict)
        and evidence.get("mode") == "direct"
        and evidence.get("public_witness") is True
    )


def _repair_clusters(failures: list[dict[str, Any]]) -> list[str]:
    """Group related public API findings by their closest failed owner."""

    module_paths = {
        str(item.get("target") or "")
        for item in failures
        if item.get("category") == "api"
        and isinstance(item.get("evidence"), dict)
        and item["evidence"].get("kind") == "module"
    }
    clusters: set[str] = set()
    for item in failures:
        category = str(item.get("category") or "")
        check_id = str(item.get("id") or "")
        target = str(item.get("target") or "")
        if check_id in {"submission.exists", "submission.python_files"}:
            clusters.add("submission:bootstrap")
            continue
        if category in {"api", "signature"}:
            owner = next(
                (
                    path
                    for path in sorted(module_paths, key=len, reverse=True)
                    if target == path or target.startswith(f"{path}.")
                ),
                "",
            )
            if not owner:
                parts = target.split(".")
                owner = (
                    "featurelifted.__root__"
                    if len(parts) <= 2 and parts[:1] == ["featurelifted"]
                    else ".".join(parts[:-1]) or target or check_id
                )
            clusters.add(f"api:{owner}")
            continue
        if category == "behavior":
            clusters.add(f"behavior:{check_id}")
            continue
        clusters.add(f"{category}:{check_id}")
    return sorted(clusters)


def decide_repair(
    workspace_dir: str | Path,
    check_result: dict[str, Any],
    *,
    lite: bool,
    frozen_v1: bool = False,
    rescue: bool = False,
    rescue_plus: bool = False,
    v3: bool = False,
) -> dict[str, Any]:
    """Return a deterministic decision without consulting evaluator information."""

    requested = bool(check_result.get("repair_needed"))
    decision: dict[str, Any] = {
        "policy_version": (
            V3_POLICY_VERSION
            if v3
            else LITE_RESCUE_PLUS_POLICY_VERSION
            if rescue_plus
            else LITE_V1_POLICY_VERSION
            if frozen_v1
            else LITE_RESCUE_POLICY_VERSION
            if rescue
            else LITE_POLICY_VERSION
            if lite
            else "contract_closure_gate.v1"
        ),
        "requested": requested,
        "eligible": requested,
        "reason": "checker did not request repair" if not requested else "repair requested",
        "repair_kind": "defect_repair" if requested else "none",
    }
    if frozen_v1 or not (lite or v3 or rescue_plus):
        return decision
    if not requested and not rescue_plus:
        return decision

    workspace = Path(workspace_dir).resolve()
    python_files = sorted((workspace / "submission").rglob("*.py"))
    if not python_files and not rescue_plus:
        return {
            **decision,
            "eligible": False,
            "reason": "empty submission is not eligible for bounded local repair",
            "python_file_count": 0,
        }

    defect_failures = [
        item
        for item in check_result.get("checks", [])
        if isinstance(item, dict)
        and item.get("status") == "fail"
        and item.get("severity") == "hard"
    ]
    if v3:
        defect_failures.extend(
            item
            for item in check_result.get("checks", [])
            if isinstance(item, dict) and _actionable_behavior_failure(item)
        )
    elif rescue_plus:
        defect_failures.extend(
            item
            for item in check_result.get("checks", [])
            if isinstance(item, dict) and _actionable_public_witness_failure(item)
        )
    evidence_failures: list[dict[str, Any]] = []
    if rescue_plus:
        evidence_failures.extend(
            item
            for item in check_result.get("checks", [])
            if isinstance(item, dict) and _repairable_evidence_failure(item)
        )
    repair_kind = "defect_repair" if defect_failures else "none"
    # A single bounded round must have one purpose. Implementation defects take
    # precedence; missing smoke evidence remains visible in the final report.
    failed = defect_failures
    categories = sorted({str(item.get("category") or "") for item in failed})
    decision.update(
        {
            "repair_kind": repair_kind,
            "requested": bool(defect_failures),
            "python_file_count": len(python_files),
            "hard_failure_count": len(failed),
            "defect_failure_count": len(defect_failures),
            "evidence_failure_count": len(evidence_failures),
            "failure_categories": categories,
        }
    )
    if not failed:
        return {
            **decision,
            "eligible": False,
            "reason": (
                "missing or invalid witness evidence is telemetry only; no paid repair"
                if evidence_failures
                else "no executable public-witness or structural defect is available for repair"
            ),
        }
    if any(item.get("id") == "submission.compile" for item in failed):
        return {
            **decision,
            "eligible": False,
            "reason": "non-compiling submissions are too broad for bounded repair",
        }
    allowed_categories = (
        _LITE_RESCUE_PLUS_REPAIR_CATEGORIES
        if rescue_plus
        else _V3_REPAIR_CATEGORIES
        if v3
        else _LOCAL_REPAIR_CATEGORIES
    )
    if any(category not in allowed_categories for category in categories):
        return {
            **decision,
            "eligible": False,
            "reason": "failure category is not eligible for bounded local repair",
        }
    if len(failed) > DEFAULT_LITE_MAX_REPAIR_FAILURES and not rescue_plus:
        return {
            **decision,
            "eligible": False,
            "reason": (
                f"{len(failed)} actionable failures exceed the bounded limit of "
                f"{DEFAULT_LITE_MAX_REPAIR_FAILURES}"
            ),
        }
    missing_api_count = sum(
        item.get("category") == "api" and item.get("status") == "fail"
        for item in failed
    )
    decision["missing_api_count"] = missing_api_count
    if rescue_plus:
        clusters = _repair_clusters(failed)
        decision["repair_clusters"] = clusters
        decision["repair_cluster_count"] = len(clusters)
        if python_files and len(clusters) > DEFAULT_RESCUE_PLUS_MAX_REPAIR_CLUSTERS:
            return {
                **decision,
                "eligible": False,
                "reason": (
                    f"{len(clusters)} repair clusters exceed the bounded limit of "
                    f"{DEFAULT_RESCUE_PLUS_MAX_REPAIR_CLUSTERS}"
                ),
            }
    elif missing_api_count > DEFAULT_LITE_MAX_MISSING_APIS:
        return {
            **decision,
            "eligible": False,
            "reason": (
                f"{missing_api_count} missing APIs exceed the bounded limit of "
                f"{DEFAULT_LITE_MAX_MISSING_APIS}"
            ),
        }
    return {
        **decision,
        "eligible": True,
        "reason": (
            "empty submission bootstrap from the public API contract"
            if not python_files
            else "selected direct public-witness mismatch"
            if rescue_plus and "behavior" in categories
            else "small, concrete public-behavior mismatch"
            if v3 and "behavior" in categories
            else "small, local, structurally repairable public-contract gap"
        ),
    }
