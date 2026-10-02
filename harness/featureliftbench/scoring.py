"""Scoring helpers."""

from __future__ import annotations

from typing import Any


def functional_gate(
    *,
    build_pass: bool,
    public_tests_pass: bool | None = None,
    hidden_tests_pass: bool | None = None,
    isolation_pass: bool | None = None,
    test_pass: bool | None = None,
    original_import_pass: bool | None = None,
) -> float:
    """Return 1.0 only when Build ∧ Public ∧ Hidden ∧ Isolation passes.

    ``test_pass`` and ``original_import_pass`` remain accepted for readers of
    historical result payloads.  New evaluations must pass the four explicit
    gates.
    """

    public_ok = bool(test_pass) if public_tests_pass is None else bool(public_tests_pass)
    hidden_ok = bool(test_pass) if hidden_tests_pass is None else bool(hidden_tests_pass)
    isolation_ok = (
        bool(original_import_pass) if isolation_pass is None else bool(isolation_pass)
    )
    return 1.0 if build_pass and public_ok and hidden_ok and isolation_ok else 0.0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_submission(
    *,
    metrics: dict[str, int | float],
    metadata: dict[str, Any],
    functional_gate_score: float,
) -> dict[str, float]:
    """Report functional correctness and reference-relative compactness.

    ``final_score`` remains as a compatibility field, but in v2 it is exactly
    the functional gate. Compactness is independent and never multiplied into
    the functional result.
    """

    reference_loc = _reference_loc(metrics, metadata)
    submission_loc = float(metrics.get("loc", metrics.get("submitted_loc", 0)))
    reference_ratio = _reference_relative_ratio(
        submission_loc=submission_loc,
        reference_loc=reference_loc,
    )
    compactness_score = _compactness_score(
        submission_loc=submission_loc,
        reference_loc=reference_loc,
    )

    return {
        "functional_gate": functional_gate_score,
        # Compatibility alias: v2 extraction_ratio is relative to the frozen
        # reference implementation, never to the complete upstream repository.
        "extraction_ratio": round(reference_ratio, 6),
        "reference_relative_loc_ratio": round(reference_ratio, 6),
        "compactness_score": round(compactness_score, 6),
        # Compatibility alias for older suite readers. It is no longer a
        # functional × compactness composite.
        "final_score": float(functional_gate_score),
    }


def _reference_loc(
    metrics: dict[str, int | float],
    metadata: dict[str, Any],
) -> float:
    value = metrics.get("reference_loc")
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    scoring_reference = metadata.get("scoring_reference")
    if isinstance(scoring_reference, dict):
        value = scoring_reference.get("oracle_loc")
        if isinstance(value, (int, float)):
            return max(0.0, float(value))
    return 0.0


def _reference_relative_ratio(
    *,
    submission_loc: float,
    reference_loc: float,
) -> float:
    if reference_loc <= 0:
        return 0.0 if submission_loc <= 0 else 1.0
    return max(0.0, submission_loc / reference_loc)


def _compactness_score(
    *,
    submission_loc: float,
    reference_loc: float,
) -> float:
    if submission_loc <= 0:
        return 1.0 if reference_loc <= 0 else 0.0
    if reference_loc <= 0:
        return 0.0
    return clamp(reference_loc / submission_loc)
