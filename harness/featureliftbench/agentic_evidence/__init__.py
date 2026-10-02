"""Agent-adjudicated repository evidence for contract provenance audits."""

from .canaries import CANARY_CLASSES
from .canaries import generate_canary_suite
from .citation_validator import build_citation
from .citation_validator import clamp_line_range
from .citation_validator import validate_citation
from .consensus import adjudicate_records
from .direct_auditor import coerce_confidence
from .firewall import validate_evidence_pack
from .schema import AUDIT_RECORD_SCHEMA
from .schema import CONSENSUS_SCHEMA
from .schema import EVIDENCE_PACK_SCHEMA
from .schema import VERDICTS
from .schema import validate_audit_record

__all__ = [
    "AUDIT_RECORD_SCHEMA",
    "CANARY_CLASSES",
    "CONSENSUS_SCHEMA",
    "EVIDENCE_PACK_SCHEMA",
    "VERDICTS",
    "adjudicate_records",
    "build_citation",
    "clamp_line_range",
    "coerce_confidence",
    "generate_canary_suite",
    "validate_audit_record",
    "validate_citation",
    "validate_evidence_pack",
]
