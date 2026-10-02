"""Build a contract matrix from metadata.public_spec only."""

from __future__ import annotations

from typing import Any


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


def build_contract_matrix(public_spec: dict[str, Any]) -> dict[str, Any]:
    """One row per Bxxx behavior and one row per required_api path.

    Never include source_entrypoints. Isolation behaviors stay listed so the
    agent sees them, but scenario stubs are only for regular Bxxx clauses.
    """

    behaviors: list[dict[str, Any]] = []
    raw_behaviors = public_spec.get("behaviors")
    if isinstance(raw_behaviors, list):
        for item in raw_behaviors:
            if not isinstance(item, dict):
                continue
            behavior_id = str(item.get("id") or "").strip()
            text = str(item.get("text") or "").strip()
            if not behavior_id:
                continue
            behaviors.append(
                {
                    "id": behavior_id,
                    "text": text,
                    "row_kind": "behavior",
                    "needs_scenario": True,
                }
            )

    isolation = public_spec.get("isolation_behavior")
    if isinstance(isolation, dict):
        behavior_id = str(isolation.get("id") or "").strip()
        text = str(isolation.get("text") or "").strip()
        if behavior_id:
            behaviors.append(
                {
                    "id": behavior_id,
                    "text": text,
                    "row_kind": "isolation",
                    "needs_scenario": False,
                }
            )

    api_rows = [
        {
            **row,
            "row_kind": "required_api",
            "needs_scenario": False,
        }
        for row in flatten_required_api_paths(public_spec)
    ]

    return {
        "schema_version": "featureliftbench.spec_adversarial_matrix.v1",
        "title": str(public_spec.get("title") or "").strip(),
        "summary": str(public_spec.get("summary") or "").strip(),
        "behaviors": behaviors,
        "required_api": api_rows,
        "exclusions": [
            str(item).strip()
            for item in (public_spec.get("exclusions") or [])
            if str(item).strip()
        ],
        "forbidden_imports": list(
            (public_spec.get("forbidden") or {}).get("imports") or []
            if isinstance(public_spec.get("forbidden"), dict)
            else []
        ),
    }


def scenario_behavior_ids(matrix: dict[str, Any]) -> list[str]:
    """Behavior IDs that need a filled contract_cases stub."""

    return [
        str(row["id"])
        for row in matrix.get("behaviors") or []
        if isinstance(row, dict) and row.get("needs_scenario") and row.get("id")
    ]
