"""Append-only claim/evidence ledger with revision freshness gates."""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .hashing import canonical_json, digest_json
from .storage import JsonlGraphStore


CLAIM_SCHEMA = "featureliftbench.repo_graph.claim.v1"
EVIDENCE_SCHEMA = "featureliftbench.repo_graph.evidence.v1"
CLAIM_STATUSES = frozenset({"hypothesis", "observed", "verified", "contradicted", "stale"})
CLASSIFICATIONS = frozenset(
    {"required", "replaceable", "incidental", "optional", "unresolved", "excluded"}
)
EVIDENCE_STATUSES = frozenset({"supports", "contradicts", "inconclusive", "failed"})
EVIDENCE_CLASSES = frozenset(
    {"static", "runtime", "public_test", "clean_install", "api_probe", "resource_probe"}
)
_SENSITIVE_RE = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*\S+"
)


class RepoGraphLedger:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.claims_path = self.root / "semantic_claims.jsonl"
        self.evidence_path = self.root / "runtime_evidence.jsonl"
        self.lock_path = self.root / ".ledger.lock"

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.claims_path.touch(exist_ok=True)
        self.evidence_path.touch(exist_ok=True)

    def add_claim(
        self,
        *,
        subject: str,
        predicate: str,
        object_value: str = "",
        classification: str = "unresolved",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        self.initialize()
        subject = _bounded_text(subject, "subject", 500)
        self._validate_subject(subject)
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown claim classification: {classification}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("claim confidence must be between 0 and 1")
        predicate = _bounded_text(predicate, "predicate", 120)
        object_value = _bounded_optional_text(object_value, "object", 300)
        with self._lock():
            states = self.claim_states()
            claim_id = _next_id("claim", states)
            revision = self.current_revision()
            record = {
                "schema_version": CLAIM_SCHEMA,
                "claim_id": claim_id,
                "event": "created",
                "subject": subject,
                "predicate": predicate,
                "object": object_value,
                "classification": classification,
                "status": "hypothesis",
                "confidence": confidence,
                "evidence_ids": [],
                "submission_revision": revision,
                "snapshot_id": self.snapshot_id(),
                "environment_scope_hash": self.environment_scope_hash(),
            }
            self._append(self.claims_path, record)
        return record

    def update_claim(
        self,
        claim_id: str,
        *,
        status: str,
        evidence_ids: Iterable[str] = (),
        classification: str | None = None,
    ) -> dict[str, Any]:
        if status not in CLAIM_STATUSES:
            raise ValueError(f"unknown claim status: {status}")
        if classification is not None and classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown claim classification: {classification}")
        with self._lock():
            states = self.claim_states()
            previous = states.get(claim_id)
            if previous is None:
                raise ValueError(f"unknown claim: {claim_id}")
            linked = list(dict.fromkeys([*previous.get("evidence_ids", []), *evidence_ids]))
            evidence = self.evidence_states()
            missing = [evidence_id for evidence_id in linked if evidence_id not in evidence]
            if missing:
                raise ValueError(f"unknown evidence: {', '.join(missing)}")
            revision = self.current_revision()
            current_evidence = [
                evidence[evidence_id]
                for evidence_id in linked
                if self._evidence_is_fresh(evidence[evidence_id], revision)
            ]
            supports = [item for item in current_evidence if item.get("status") == "supports"]
            contradicts = [item for item in current_evidence if item.get("status") == "contradicts"]
            if status == "observed" and not supports:
                raise ValueError("observed requires one supporting evidence record at current revision")
            if status == "verified" and len({item.get("evidence_class") for item in supports}) < 2:
                raise ValueError("verified requires two independent evidence classes at current revision")
            if status == "contradicted" and not contradicts:
                raise ValueError("contradicted requires current contradicting evidence")
            record = {
                **previous,
                "event": "status_updated",
                "status": status,
                "classification": classification or previous.get("classification", "unresolved"),
                "evidence_ids": linked,
                "submission_revision": revision,
                "environment_scope_hash": self.environment_scope_hash(),
            }
            self._append(self.claims_path, record)
        return record

    def record_evidence(
        self,
        *,
        kind: str,
        probe_type: str,
        evidence_class: str,
        status: str,
        result_summary: str,
        input_summary: str = "",
        command: str = "",
        claim_ids: Iterable[str] = (),
        affected_symbols: Iterable[str] = (),
    ) -> dict[str, Any]:
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"unknown evidence class: {evidence_class}")
        if status not in EVIDENCE_STATUSES:
            raise ValueError(f"unknown evidence status: {status}")
        kind = _bounded_text(kind, "kind", 80)
        probe_type = _bounded_text(probe_type, "probe_type", 120)
        input_summary = _bounded_optional_text(input_summary, "input_summary", 500)
        result_summary = _bounded_text(result_summary, "result_summary", 500)
        linked_claims = list(dict.fromkeys(claim_ids))
        symbols = list(dict.fromkeys(affected_symbols))[:100]
        with self._lock():
            states = self.claim_states()
            missing = [claim_id for claim_id in linked_claims if claim_id not in states]
            if missing:
                raise ValueError(f"unknown claim: {', '.join(missing)}")
            evidence_states = self.evidence_states()
            evidence_id = _next_id("evidence", evidence_states)
            record = {
                "schema_version": EVIDENCE_SCHEMA,
                "evidence_id": evidence_id,
                "kind": kind,
                "probe_type": probe_type,
                "evidence_class": evidence_class,
                "status": status,
                "input_summary": input_summary,
                "result_summary": result_summary,
                "result_hash": hashlib.sha256(result_summary.encode("utf-8")).hexdigest(),
                "command_hash": hashlib.sha256(command.encode("utf-8")).hexdigest() if command else "",
                "claim_ids": linked_claims,
                "affected_symbols": symbols,
                "submission_revision": self.current_revision(),
                "snapshot_id": self.snapshot_id(),
                "environment_scope_hash": self.environment_scope_hash(),
                "freshness": "fresh",
            }
            self._append(self.evidence_path, record)
        return record

    def invalidate_for_revision(self, revision: int) -> list[str]:
        if not self.claims_path.is_file():
            return []
        stale_ids = []
        with self._lock():
            for claim_id, previous in self.claim_states().items():
                if previous.get("status") in {"stale", "contradicted"}:
                    continue
                if int(previous.get("submission_revision", -1)) == revision:
                    continue
                record = {
                    **previous,
                    "event": "revision_invalidated",
                    "status": "stale",
                    "submission_revision": revision,
                    "stale_reason": "submission_revision_changed",
                }
                self._append(self.claims_path, record)
                stale_ids.append(claim_id)
        return stale_ids

    def claim_states(self) -> dict[str, dict[str, Any]]:
        return _latest_records(self.claims_path, "claim_id")

    def evidence_states(self) -> dict[str, dict[str, Any]]:
        return _latest_records(self.evidence_path, "evidence_id")

    def freshness_report(self) -> dict[str, Any]:
        revision = self.current_revision()
        claims = self.claim_states()
        evidence = self.evidence_states()
        stale_claims = [
            claim_id
            for claim_id, claim in claims.items()
            if claim.get("status") == "stale"
            or int(claim.get("submission_revision", -1)) != revision
            or claim.get("environment_scope_hash") != self.environment_scope_hash()
        ]
        fresh_evidence = [
            evidence_id
            for evidence_id, record in evidence.items()
            if self._evidence_is_fresh(record, revision)
        ]
        return {
            "schema_version": "featureliftbench.repo_graph.freshness.v1",
            "submission_revision": revision,
            "environment_scope_hash": self.environment_scope_hash(),
            "claim_count": len(claims),
            "evidence_count": len(evidence),
            "stale_claims": sorted(stale_claims),
            "fresh_evidence": sorted(fresh_evidence),
            "fresh": not stale_claims,
        }

    def stopping_guard(self) -> dict[str, Any]:
        freshness = self.freshness_report()
        claims = self.claim_states()
        evidence = self.evidence_states()
        revision = self.current_revision()
        unresolved = sorted(
            claim_id
            for claim_id, claim in claims.items()
            if claim.get("classification") == "unresolved"
            and claim.get("status") != "contradicted"
        )
        pending_prune = sorted(
            claim_id
            for claim_id, claim in claims.items()
            if claim.get("classification") in {"incidental", "excluded"}
            and claim.get("status") not in {"observed", "verified", "contradicted"}
        )
        final_verification = any(
            item.get("probe_type") == "final_verification"
            and item.get("status") == "supports"
            and self._evidence_is_fresh(item, revision)
            for item in evidence.values()
        )
        blockers = []
        if freshness["stale_claims"]:
            blockers.append("stale_claims")
        if unresolved:
            blockers.append("unresolved_claims")
        if pending_prune:
            blockers.append("pending_prune")
        if not final_verification:
            blockers.append("missing_fresh_final_verification")
        return {
            "schema_version": "featureliftbench.repo_graph.stopping_guard.v1",
            "ready": not blockers,
            "blockers": blockers,
            "stale_claims": freshness["stale_claims"],
            "unresolved_claims": unresolved,
            "pending_prune_claims": pending_prune,
            "fresh_final_verification": final_verification,
            "submission_revision": revision,
        }

    def current_revision(self) -> int:
        state = _read_json(self.root / "submission_state.json")
        revision = state.get("revision", 0)
        return revision if isinstance(revision, int) and revision >= 0 else 0

    def snapshot_id(self) -> str:
        return str(_read_json(self.root / "base" / "manifest.json").get("snapshot_id", ""))

    def environment_scope_hash(self) -> str:
        overlay = _read_json(self.root / "task_overlay.json")
        return digest_json(overlay.get("environment_scope", {}))

    def _validate_subject(self, subject: str) -> None:
        subject = _bounded_text(subject, "subject", 500)
        if subject.startswith("behavior:"):
            overlay = _read_json(self.root / "task_overlay.json")
            behavior_ids = {
                item.get("id") for item in overlay.get("behaviors", []) if isinstance(item, dict)
            }
            if subject not in behavior_ids:
                raise ValueError(f"unknown behavior subject: {subject}")
            return
        snapshot = JsonlGraphStore().load(self.root / "base")
        if subject not in {node.stable_id for node in snapshot.nodes}:
            raise ValueError(f"unknown graph subject: {subject}")

    def _evidence_is_fresh(self, evidence: dict[str, Any], revision: int) -> bool:
        return (
            int(evidence.get("submission_revision", -1)) == revision
            and evidence.get("environment_scope_hash") == self.environment_scope_hash()
            and evidence.get("snapshot_id") == self.snapshot_id()
        )

    def _append(self, path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")

    def _lock(self):
        return _FileLock(self.lock_path)


class _FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def __enter__(self) -> _FileLock:
        self.handle = self.path.open("a+b")
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *_args: object) -> None:
        assert self.handle is not None
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


def _latest_records(path: Path, key: str) -> dict[str, dict[str, Any]]:
    result = {}
    if not path.is_file():
        return result
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid ledger JSONL {path.name}:{line_number}") from exc
        if not isinstance(record, dict) or not isinstance(record.get(key), str):
            raise ValueError(f"invalid ledger record {path.name}:{line_number}")
        result[record[key]] = record
    return result


def _next_id(prefix: str, records: dict[str, dict[str, Any]]) -> str:
    numbers = []
    for identifier in records:
        if identifier.startswith(f"{prefix}_"):
            try:
                numbers.append(int(identifier.rsplit("_", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}_{max(numbers, default=0) + 1:04d}"


def _bounded_text(value: str, name: str, max_chars: int) -> str:
    text = " ".join(str(value).split())
    if not text:
        raise ValueError(f"{name} must not be empty")
    if len(text) > max_chars:
        raise ValueError(f"{name} exceeds {max_chars} characters")
    if _SENSITIVE_RE.search(text):
        raise ValueError(f"{name} appears to contain sensitive credential material")
    return text


def _bounded_optional_text(value: str, name: str, max_chars: int) -> str:
    text = " ".join(str(value).split())
    if not text:
        return ""
    if len(text) > max_chars:
        raise ValueError(f"{name} exceeds {max_chars} characters")
    if _SENSITIVE_RE.search(text):
        raise ValueError(f"{name} appears to contain sensitive credential material")
    return text


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value
