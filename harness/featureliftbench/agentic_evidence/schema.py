"""Strict, dependency-free schemas for agentic evidence artifacts."""

from __future__ import annotations

from typing import Any, Mapping


AUDIT_RECORD_SCHEMA = "featureliftbench.agentic_evidence.audit_record.v1"
CONSENSUS_SCHEMA = "featureliftbench.agentic_evidence.consensus.v1"
EVIDENCE_PACK_SCHEMA = "featureliftbench.agentic_evidence.pack.v1"
FLASH33_CONSENSUS_LABELS_SCHEMA = (
    "featureliftbench.hidden_provenance_labels.agent_consensus.v1"
)
FLASH33_AGREEMENT_SCHEMA = "featureliftbench.agentic_evidence.flash33_agreement.v1"

VERDICTS = frozenset(
    {"explicit", "recoverable", "ambiguous", "underdetermined", "abstain"}
)
EVIDENCE_REQUIRED_VERDICTS = frozenset({"explicit", "recoverable", "ambiguous"})
PUBLIC_EVIDENCE_KINDS = frozenset({"task", "public_spec", "repository"})


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_evidence_reference(value: Any, *, field: str = "evidence") -> list[str]:
    errors: list[str] = []
    if not isinstance(value, Mapping):
        return [f"{field} must be an object"]
    path = value.get("path")
    if not _non_empty_string(path):
        errors.append(f"{field}.path must be a non-empty string")
    kind = value.get("kind")
    if kind not in PUBLIC_EVIDENCE_KINDS:
        errors.append(
            f"{field}.kind must be one of {sorted(PUBLIC_EVIDENCE_KINDS)}"
        )
    start = value.get("start_line")
    end = value.get("end_line")
    if not isinstance(start, int) or isinstance(start, bool) or start < 1:
        errors.append(f"{field}.start_line must be a positive integer")
    if not isinstance(end, int) or isinstance(end, bool) or end < 1:
        errors.append(f"{field}.end_line must be a positive integer")
    if isinstance(start, int) and isinstance(end, int) and end < start:
        errors.append(f"{field}.end_line must be >= start_line")
    digest = value.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append(f"{field}.sha256 must be a 64-character digest")
    elif any(ch not in "0123456789abcdef" for ch in digest.lower()):
        errors.append(f"{field}.sha256 must be hexadecimal")
    if not _non_empty_string(value.get("claim")):
        errors.append(f"{field}.claim must be a non-empty string")
    quote = value.get("quote")
    if quote is not None and not isinstance(quote, str):
        errors.append(f"{field}.quote must be a string when present")
    return errors


def validate_audit_record(record: Any) -> list[str]:
    """Validate one assertion-level Agent audit record."""

    if not isinstance(record, Mapping):
        return ["audit record must be an object"]
    errors: list[str] = []
    if record.get("schema_version") != AUDIT_RECORD_SCHEMA:
        errors.append(f"schema_version must be {AUDIT_RECORD_SCHEMA!r}")
    for field in ("task_id", "nodeid", "agent_id"):
        if not _non_empty_string(record.get(field)):
            errors.append(f"{field} must be a non-empty string")
    verdict = record.get("verdict")
    if verdict not in VERDICTS:
        errors.append(f"verdict must be one of {sorted(VERDICTS)}")
    confidence = record.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0.0 <= float(confidence) <= 1.0
    ):
        errors.append("confidence must be a number in [0, 1]")
    obligations = record.get("public_obligation_ids")
    if not isinstance(obligations, list) or any(
        not _non_empty_string(item) for item in obligations
    ):
        errors.append("public_obligation_ids must be a list of non-empty strings")
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []
    for index, item in enumerate(evidence):
        errors.extend(validate_evidence_reference(item, field=f"evidence[{index}]"))
    counterevidence = record.get("counterevidence")
    if not isinstance(counterevidence, list):
        errors.append("counterevidence must be a list")
        counterevidence = []
    for index, item in enumerate(counterevidence):
        errors.extend(
            validate_evidence_reference(item, field=f"counterevidence[{index}]")
        )
    if verdict in EVIDENCE_REQUIRED_VERDICTS and not evidence:
        errors.append(f"verdict {verdict!r} requires at least one evidence citation")
    if verdict == "ambiguous" and not counterevidence:
        errors.append("ambiguous verdict requires at least one counterevidence citation")
    if verdict == "abstain" and not _non_empty_string(record.get("abstain_reason")):
        errors.append("abstain verdict requires abstain_reason")
    return errors


def validate_evidence_pack_shape(pack: Any) -> list[str]:
    """Validate the public, Hidden-blind evidence-pack envelope."""

    if not isinstance(pack, Mapping):
        return ["evidence pack must be an object"]
    errors: list[str] = []
    if pack.get("schema_version") != EVIDENCE_PACK_SCHEMA:
        errors.append(f"schema_version must be {EVIDENCE_PACK_SCHEMA!r}")
    for field in ("task_id", "generator_id"):
        if not _non_empty_string(pack.get(field)):
            errors.append(f"{field} must be a non-empty string")
    if pack.get("information_boundary") != "task_public_spec_repo_only":
        errors.append(
            "information_boundary must be 'task_public_spec_repo_only'"
        )
    entries = pack.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be a list")
        entries = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            errors.append(f"entries[{index}] must be an object")
            continue
        if not _non_empty_string(entry.get("title")):
            errors.append(f"entries[{index}].title must be a non-empty string")
        citations = entry.get("citations")
        if not isinstance(citations, list) or not citations:
            errors.append(f"entries[{index}].citations must be a non-empty list")
            continue
        for citation_index, citation in enumerate(citations):
            errors.extend(
                validate_evidence_reference(
                    citation,
                    field=f"entries[{index}].citations[{citation_index}]",
                )
            )
    return errors
