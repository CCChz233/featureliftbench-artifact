"""Sufficiency, PSF, and inclusion flags from a reconstructed timeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .constants import ACCOUNTING_TOTAL, RUN_METRICS_FIELDS, METHOD_VERSION
from .evaluate import SnapshotEvaluation
from .ledger import RunLedger
from .replay import ReplayOutcome, TimelineState
from .scope import OfficialRun


@dataclass
class RunMetrics:
    values: dict[str, Any]

    def to_row(self) -> dict[str, Any]:
        return {field: self.values.get(field) for field in RUN_METRICS_FIELDS}


def compute_run_metrics(
    *,
    run: OfficialRun,
    identity_status: str,
    ledger: RunLedger,
    replay: ReplayOutcome | None,
    evaluations: Mapping[str, SnapshotEvaluation],
    final_eval_matches: bool | None,
) -> RunMetrics:
    notes: list[str] = []
    original_steps = run.original_steps
    unique_states = len(replay.unique_hashes) if replay else 0
    evaluated = sum(
        1
        for digest in (replay.unique_hashes if replay else [])
        if digest in evaluations and evaluations[digest].eval_status == "ok"
    )
    unresolved_states = unique_states - evaluated
    eval_by_hash = evaluations
    timeline = replay.timeline if replay else []

    sufficiency = "unresolved"
    first_pass_index = None
    first_pass_hash = None
    first_pass_tokens = None
    first_pass_lower = None
    first_pass_upper = None
    first_pass_fraction = None
    post_tokens = None
    post_fraction = None
    post_lower = None
    post_upper = None
    post_mutations = None
    post_failure_seen = None
    ever_pass_final_fail = None
    stable_index = None
    stable_tokens = None
    stable_post = None
    stable_status = "unresolved"
    full_timeline = bool(replay and replay.full_timeline_covered)
    unknown_before_first_pass = False

    pass_indices: list[int] = []
    for state in timeline:
        evaluation = eval_by_hash.get(state.artifact_hash)
        if evaluation is None or evaluation.eval_status != "ok":
            if first_pass_index is None:
                unknown_before_first_pass = True
            continue
        if evaluation.functional_pass is True:
            pass_indices.append(state.state_index)
            if first_pass_index is None:
                first_pass_index = state.state_index
                first_pass_hash = state.artifact_hash
                first_pass_tokens = state.cumulative_tokens
                first_pass_lower = state.cumulative_tokens_lower
                first_pass_upper = state.cumulative_tokens_upper

    if replay is None:
        sufficiency = "unresolved"
        notes.append("no_replay")
    elif not timeline:
        sufficiency = "unresolved"
        notes.append(replay.error or "empty_timeline")
    elif first_pass_index is None:
        if full_timeline and unresolved_states == 0 and unique_states == evaluated:
            sufficiency = "never_sufficient"
        else:
            sufficiency = "unresolved"
            notes.append("incomplete_or_unevaluated_states")
    elif unknown_before_first_pass or not full_timeline:
        sufficiency = "bounded"
        notes.append("earliest_observed_pass_only")
    else:
        token_exact = (
            first_pass_lower is not None
            and first_pass_upper is not None
            and first_pass_lower == first_pass_upper
            and ledger.token_usage_status == "complete"
            and ledger.token_alignment_status == "exact"
        )
        if token_exact and first_pass_tokens is None:
            first_pass_tokens = first_pass_lower
        sufficiency = "exact" if token_exact else "bounded"
        if not token_exact:
            notes.append("state_known_token_imprecise_or_missing")

    total = ledger.total_tokens
    if sufficiency in {"exact", "bounded"} and first_pass_index is not None:
        if (
            total
            and total > 0
            and first_pass_tokens is not None
            and sufficiency == "exact"
        ):
            first_pass_fraction = first_pass_tokens / total
            post_tokens = total - first_pass_tokens
            post_fraction = post_tokens / total
        elif total and total > 0 and first_pass_lower is not None and first_pass_upper is not None:
            first_pass_fraction = None
            post_lower = 1 - (first_pass_upper / total)
            post_upper = 1 - (first_pass_lower / total)
            post_fraction = None
            if first_pass_tokens is not None:
                post_tokens = total - first_pass_tokens

        post_mutations = 0
        post_failure_seen = False
        last_hash = None
        for state in timeline:
            if state.state_index <= (first_pass_index or 0):
                last_hash = state.artifact_hash
                continue
            if last_hash is not None and state.artifact_hash != last_hash:
                post_mutations += 1
            last_hash = state.artifact_hash
            evaluation = eval_by_hash.get(state.artifact_hash)
            if evaluation is not None and evaluation.eval_status == "ok" and evaluation.functional_pass is False:
                post_failure_seen = True

    if run.final_pass:
        ever_pass_final_fail = False
    elif sufficiency == "unresolved":
        ever_pass_final_fail = None
    elif first_pass_index is not None:
        ever_pass_final_fail = True
    elif sufficiency == "never_sufficient":
        ever_pass_final_fail = False
    else:
        ever_pass_final_fail = None

    if run.final_pass and sufficiency in {"exact", "bounded"} and full_timeline and unresolved_states == 0:
        stable_status, stable_index, stable_tokens, stable_post = _stable_pass(
            timeline, eval_by_hash, total
        )
    elif run.final_pass:
        stable_status = "unresolved"

    include_psf = bool(
        run.final_pass
        and identity_status == "ok"
        and final_eval_matches is True
        and replay is not None
        and replay.full_timeline_covered
        and sufficiency == "exact"
        and ledger.token_usage_status == "complete"
        and ledger.token_alignment_status == "exact"
        and unresolved_states == 0
        and replay.last_matches_disk
        and ledger.accounting_basis == ACCOUNTING_TOTAL
        and ledger.total_tokens
        and ledger.total_tokens > 0
        and first_pass_tokens is not None
    )
    psf_reason = ""
    if not include_psf:
        psf_reason = _psf_reason(
            run=run,
            identity_status=identity_status,
            final_eval_matches=final_eval_matches,
            replay=replay,
            sufficiency=sufficiency,
            ledger=ledger,
        )

    include_effort = bool(
        identity_status == "ok"
        and ledger.token_usage_status == "complete"
        and ledger.total_tokens is not None
        and ledger.total_tokens > 0
    )
    effort_reason = "" if include_effort else (
        "identity" if identity_status != "ok" else ledger.missing_reason or "token_usage_incomplete"
    )

    include_failure = bool(
        not run.final_pass
        and identity_status == "ok"
        and replay is not None
        and final_eval_matches is True
        and replay.full_timeline_covered
        and unresolved_states == 0
        and sufficiency in {"exact", "bounded", "never_sufficient"}
    )
    failure_reason = ""
    if run.final_pass:
        failure_reason = "final_success_not_in_failure_history"
    elif not include_failure:
        failure_reason = "incomplete_failure_history"

    values = {
        "method_version": METHOD_VERSION,
        "run_id": run.run_id,
        "configuration": run.configuration,
        "task_id": run.task_id,
        "lift_type": run.lift_type,
        "final_pass": run.final_pass,
        "identity_status": identity_status,
        "replay_status": replay.reconstruction_status if replay else "unresolved",
        "final_tree_matches": replay.last_matches_disk if replay else None,
        "final_eval_matches": final_eval_matches,
        "full_timeline_covered": full_timeline,
        "unique_states": unique_states,
        "evaluated_states": evaluated,
        "unresolved_states": unresolved_states,
        "accounting_basis": ledger.accounting_basis,
        "token_usage_status": ledger.token_usage_status,
        "token_alignment_status": ledger.token_alignment_status,
        "total_tokens": ledger.total_tokens,
        "original_steps": original_steps,
        "sufficiency_status": sufficiency,
        "first_pass_state_index": first_pass_index,
        "first_pass_hash": first_pass_hash,
        "first_pass_tokens": first_pass_tokens,
        "first_pass_tokens_lower": first_pass_lower,
        "first_pass_tokens_upper": first_pass_upper,
        "first_pass_fraction": first_pass_fraction,
        "post_sufficiency_tokens": post_tokens,
        "post_sufficiency_fraction": post_fraction,
        "post_sufficiency_fraction_lower": post_lower,
        "post_sufficiency_fraction_upper": post_upper,
        "post_sufficiency_mutations": post_mutations,
        "post_sufficiency_failure_seen": post_failure_seen,
        "ever_pass_final_fail": ever_pass_final_fail,
        "stable_first_pass_state_index": stable_index,
        "stable_first_pass_tokens": stable_tokens,
        "stable_post_fraction": stable_post,
        "stable_status": stable_status,
        "include_psf_primary": include_psf,
        "include_effort": include_effort,
        "include_failure_history": include_failure,
        "exclusion_reason_psf_primary": psf_reason,
        "exclusion_reason_effort": effort_reason,
        "exclusion_reason_failure_history": failure_reason,
        "missing_reason": replay.error if replay and replay.error else ledger.missing_reason,
        "notes": "; ".join(notes),
    }
    return RunMetrics(values)


def _stable_pass(
    timeline: list[TimelineState],
    evaluations: Mapping[str, SnapshotEvaluation],
    total: int | None,
) -> tuple[str, int | None, int | None, float | None]:
    labeled: list[tuple[TimelineState, bool | None]] = []
    for state in timeline:
        evaluation = evaluations.get(state.artifact_hash)
        if evaluation is None or evaluation.eval_status != "ok":
            return "unresolved", None, None, None
        labeled.append((state, evaluation.functional_pass))
    stable = None
    for index, (state, passed) in enumerate(labeled):
        if passed and all(item[1] for item in labeled[index:]):
            stable = state
            break
    if stable is None:
        return "never_stable", None, None, None
    post = None
    if total and total > 0 and stable.cumulative_tokens is not None:
        post = (total - stable.cumulative_tokens) / total
    return "exact", stable.state_index, stable.cumulative_tokens, post


def _psf_reason(
    *,
    run: OfficialRun,
    identity_status: str,
    final_eval_matches: bool | None,
    replay: ReplayOutcome | None,
    sufficiency: str,
    ledger: RunLedger,
) -> str:
    if not run.final_pass:
        return "final_fail"
    if identity_status != "ok":
        return f"identity:{identity_status}"
    if final_eval_matches is not True:
        return "final_eval_mismatch_or_missing"
    if replay is None or not replay.full_timeline_covered:
        return "timeline_incomplete"
    if sufficiency != "exact":
        return f"sufficiency:{sufficiency}"
    if ledger.token_usage_status != "complete" or not ledger.total_tokens:
        return "token_usage_incomplete"
    return "token_alignment_or_total"
