"""Build an obligation ledger from metadata.public_spec only.

Rows are required_api paths and Bxxx clauses (including isolation). The harness
never writes tests, stubs, expected values, or source_entrypoints.
"""

from __future__ import annotations

from typing import Any

from .common import LEDGER_SCHEMA
from .common import VERIFICATION_UNSET


def flatten_required_api_paths(public_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten required_api entries and nested members into path rows."""

    rows: list[dict[str, Any]] = []
    required = public_spec.get("required_api")
    if not isinstance(required, list):
        return rows
    for entry in required:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        rows.append(
            {
                "path": path,
                "kind": str(entry.get("kind") or "").strip() or "symbol",
                "signature": str(entry.get("signature") or "").strip(),
            }
        )
        members = entry.get("members")
        if not isinstance(members, list):
            continue
        for member in members:
            if not isinstance(member, dict):
                continue
            member_path = str(member.get("path") or "").strip()
            if not member_path:
                continue
            rows.append(
                {
                    "path": member_path,
                    "kind": str(member.get("kind") or "").strip() or "member",
                    "signature": str(member.get("signature") or "").strip(),
                }
            )
    return rows


def _empty_evidence() -> dict[str, str]:
    return {"path": "", "symbol": "", "note": ""}


def _empty_verification() -> dict[str, str]:
    return {"status": VERIFICATION_UNSET, "citation": ""}


def _api_obligation(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row["path"])
    kind = str(row.get("kind") or "symbol")
    signature = str(row.get("signature") or "").strip()
    requirement = f"Export `{path}`"
    if kind:
        requirement += f" ({kind})"
    if signature:
        requirement += f" with signature `{signature}`"
    return {
        "id": f"API:{path}",
        "kind": "required_export",
        "requirement": requirement,
        "contract_ref": path,
        "repo_evidence": _empty_evidence(),
        "implementation": _empty_evidence(),
        "verification": _empty_verification(),
    }


def _behavior_obligation(item: dict[str, Any], *, row_kind: str) -> dict[str, Any] | None:
    behavior_id = str(item.get("id") or "").strip()
    text = str(item.get("text") or "").strip()
    if not behavior_id:
        return None
    return {
        "id": behavior_id,
        "kind": row_kind,
        "requirement": text or behavior_id,
        "contract_ref": behavior_id,
        "repo_evidence": _empty_evidence(),
        "implementation": _empty_evidence(),
        "verification": _empty_verification(),
    }


def build_obligation_ledger(public_spec: dict[str, Any]) -> dict[str, Any]:
    """One frozen row per required_api path and each public Bxxx clause."""

    obligations: list[dict[str, Any]] = []
    for row in flatten_required_api_paths(public_spec):
        obligations.append(_api_obligation(row))

    raw_behaviors = public_spec.get("behaviors")
    if isinstance(raw_behaviors, list):
        for item in raw_behaviors:
            if not isinstance(item, dict):
                continue
            row = _behavior_obligation(item, row_kind="behavior")
            if row is not None:
                obligations.append(row)

    isolation = public_spec.get("isolation_behavior")
    if isinstance(isolation, dict):
        row = _behavior_obligation(isolation, row_kind="isolation")
        if row is not None:
            obligations.append(row)

    ids = [str(row["id"]) for row in obligations]
    return {
        "schema_version": LEDGER_SCHEMA,
        "title": str(public_spec.get("title") or "").strip(),
        "summary": str(public_spec.get("summary") or "").strip(),
        "frozen_ids": ids,
        "obligations": obligations,
        "instructions": {
            "do_not_add_or_delete_rows": True,
            "do_not_invent_hidden_cases": True,
            "verification_is_path_citation_not_tests": True,
            "coverage_requires_repo_path_and_implementation_path": True,
        },
    }


def ledger_has_source_leak(payload: dict[str, Any]) -> bool:
    """True if a source_entrypoints key leaked into the ledger document."""

    dumped = _walk_keys(payload)
    return "source_entrypoints" in dumped


def _walk_keys(value: Any, found: set[str] | None = None) -> set[str]:
    keys = found if found is not None else set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            _walk_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            _walk_keys(child, keys)
    return keys
