"""Conservative consensus and abstention for independent Agent audits."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from .schema import CONSENSUS_SCHEMA
from .schema import EVIDENCE_REQUIRED_VERDICTS
from .schema import validate_audit_record


def _citation_key(value: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        value.get("kind"),
        value.get("path"),
        value.get("start_line"),
        value.get("end_line"),
        value.get("sha256"),
    )


def _abstain(
    *, task_id: str, nodeid: str, records: list[Mapping[str, Any]], reason: str
) -> dict[str, Any]:
    return {
        "schema_version": CONSENSUS_SCHEMA,
        "task_id": task_id,
        "nodeid": nodeid,
        "verdict": "abstain",
        "confidence": 0.0,
        "public_obligation_ids": [],
        "evidence": [],
        "counterevidence": [],
        "agent_ids": [str(row.get("agent_id") or "") for row in records],
        "abstain_reason": reason,
    }


def adjudicate_records(
    records: Iterable[Mapping[str, Any]],
    *,
    min_votes: int = 2,
    min_confidence: float = 0.8,
) -> dict[str, Any]:
    """Return a consensus record, abstaining on weak labels or weak evidence."""

    rows = list(records)
    task_id = str(rows[0].get("task_id") or "") if rows else ""
    nodeid = str(rows[0].get("nodeid") or "") if rows else ""
    if not rows:
        return _abstain(task_id="", nodeid="", records=[], reason="no records")
    invalid = [error for row in rows for error in validate_audit_record(row)]
    if invalid:
        return _abstain(
            task_id=task_id,
            nodeid=nodeid,
            records=rows,
            reason="invalid input records: " + "; ".join(sorted(set(invalid))),
        )
    if any(row.get("task_id") != task_id or row.get("nodeid") != nodeid for row in rows):
        return _abstain(
            task_id=task_id,
            nodeid=nodeid,
            records=rows,
            reason="records do not address the same task assertion",
        )
    counts = Counter(str(row["verdict"]) for row in rows)
    winner, votes = counts.most_common(1)[0]
    if winner == "abstain" or votes < min_votes:
        return _abstain(
            task_id=task_id,
            nodeid=nodeid,
            records=rows,
            reason=f"no verdict reached {min_votes} votes: {dict(counts)}",
        )
    agreeing = [row for row in rows if row["verdict"] == winner]
    confidence = sum(float(row["confidence"]) for row in agreeing) / len(agreeing)
    if confidence < min_confidence:
        return _abstain(
            task_id=task_id,
            nodeid=nodeid,
            records=rows,
            reason=(
                f"mean confidence {confidence:.3f} is below {min_confidence:.3f}"
            ),
        )

    citations: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in agreeing:
        for citation in row.get("evidence") or []:
            citations[_citation_key(citation)].append(citation)
    supported = [values[0] for values in citations.values() if len(values) >= min_votes]
    if winner in EVIDENCE_REQUIRED_VERDICTS and not supported:
        return _abstain(
            task_id=task_id,
            nodeid=nodeid,
            records=rows,
            reason="agreeing Agents did not share a reproducible evidence citation",
        )

    counterevidence: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    obligations: set[str] = set()
    for row in agreeing:
        obligations.update(str(value) for value in row.get("public_obligation_ids") or [])
        for citation in row.get("counterevidence") or []:
            counterevidence.setdefault(_citation_key(citation), citation)
    return {
        "schema_version": CONSENSUS_SCHEMA,
        "task_id": task_id,
        "nodeid": nodeid,
        "verdict": winner,
        "confidence": round(confidence, 6),
        "votes": votes,
        "vote_distribution": dict(sorted(counts.items())),
        "public_obligation_ids": sorted(obligations),
        "evidence": supported,
        "counterevidence": list(counterevidence.values()),
        "agent_ids": [str(row["agent_id"]) for row in agreeing],
        "abstain_reason": "",
    }
