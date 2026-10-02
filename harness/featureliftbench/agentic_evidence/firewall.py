"""Fail-closed checks that keep Hidden-aware artifacts out of method prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .citation_validator import validate_citation
from .schema import validate_evidence_pack_shape


FORBIDDEN_SUBSTRINGS = (
    "hidden_tests/",
    "hidden_tests\\",
    "hidden_stdout",
    "failed_hidden_tests",
    "eval/result.json",
    "eval\\result.json",
    "artifacts/research_analysis/hidden_provenance",
    "reports/contract_closure_200",
)
FORBIDDEN_KEYS = frozenset(
    {
        "hidden_assertion",
        "hidden_nodeid",
        "hidden_source",
        "hidden_stdout",
        "failed_hidden_tests",
        "auditor_verdict",
        "consensus_verdict",
    }
)


def _scan(value: Any, *, location: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in FORBIDDEN_KEYS:
                errors.append(f"forbidden audit-only key at {location}.{key_text}")
            errors.extend(_scan(item, location=f"{location}.{key_text}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_scan(item, location=f"{location}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden.lower() in lowered:
                errors.append(
                    f"forbidden Hidden/evaluator reference at {location}: {forbidden}"
                )
    return errors


def validate_evidence_pack(
    pack: Any,
    task_dir: str | Path,
) -> list[str]:
    errors = validate_evidence_pack_shape(pack)
    errors.extend(_scan(pack))
    if not isinstance(pack, Mapping):
        return sorted(set(errors))
    for entry_index, entry in enumerate(pack.get("entries") or []):
        if not isinstance(entry, Mapping):
            continue
        for citation_index, citation in enumerate(entry.get("citations") or []):
            if not isinstance(citation, Mapping):
                continue
            for error in validate_citation(task_dir, citation):
                errors.append(
                    f"entries[{entry_index}].citations[{citation_index}]: {error}"
                )
    return sorted(set(errors))
