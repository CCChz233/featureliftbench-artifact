"""Artifact-aware, recency, and verification-aware OpenHands condensers.

These strategies mutate the prompt view. They do not rewrite trajectory
events on disk and they do not call an LLM summarizer.
"""

from __future__ import annotations

from .roles import ARTIFACT_AWARE
from .roles import DEFAULT_ATTENTION_WINDOW
from .roles import RECENCY_MASKING
from .roles import apply_artifact_aware
from .roles import apply_recency_masking
from .roles import event_from_mapping
from .verification import VERIFICATION_AWARE
from .verification import apply_verification_aware

__all__ = [
    "ARTIFACT_AWARE",
    "DEFAULT_ATTENTION_WINDOW",
    "RECENCY_MASKING",
    "VERIFICATION_AWARE",
    "apply_artifact_aware",
    "apply_recency_masking",
    "apply_verification_aware",
    "event_from_mapping",
]
