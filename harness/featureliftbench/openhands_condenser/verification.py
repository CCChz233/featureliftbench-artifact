"""Verification-aware context compression (SDK-free).

Compress old self-test observation bodies into a compact ledger. Does not stop
the agent, does not use T*/Hidden/evaluator, and does not protect the whole
featurelifted tree the way artifact-aware retention does.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import replace
from typing import Iterable

from featureliftbench.openhands_condenser.roles import TOKEN_STUB
from featureliftbench.openhands_condenser.roles import CondenserEvent
from featureliftbench.openhands_condenser.roles import _looks_like_spec_path
from featureliftbench.token_utility_signals import PYTEST_COUNT_RE
from featureliftbench.token_utility_signals import classify
from featureliftbench.token_utility_signals import command_skeleton
from featureliftbench.token_utility_signals import outcome_fingerprint

VERIFICATION_AWARE = "verification_aware"
RECORDED_STUB = "Verification recorded."
LEDGER_HEADER = "Verification ledger:"
LEDGER_CAP = 80
# Conservative: 1 char <= 1 token. The previous 4-char heuristic under-counted
# Flash Core-12 (328k observation chars ≈ 166k billed prompt tokens).
OVERFLOW_CHARS_PER_TOKEN = 1

EXCEPTION_RE = re.compile(
    r"^([A-Za-z_][\w.]*(?:Error|Exception))\s*:",
    re.MULTILINE,
)


@dataclass(frozen=True)
class VerificationStats:
    self_test_n: int = 0
    kept_full: int = 0
    ledger_lines: int = 0
    stubbed: int = 0
    overflow_masked: int = 0
    event_n: int = 0
    estimated_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "self_test_n": self.self_test_n,
            "kept_full": self.kept_full,
            "ledger_lines": self.ledger_lines,
            "stubbed": self.stubbed,
            "overflow_masked": self.overflow_masked,
            "event_n": self.event_n,
            "estimated_tokens": self.estimated_tokens,
        }


def apply_verification_aware(
    events: Iterable[CondenserEvent],
    *,
    trigger_tokens: int | None = None,
    ledger_cap: int = LEDGER_CAP,
) -> tuple[list[CondenserEvent], VerificationStats]:
    """Replace old self-test stdout with a one-host verification ledger."""

    paired = _pair_preceding_commands(list(events))
    self_test_indices = [
        index
        for index, event in enumerate(paired)
        if event.is_observation and _is_self_test_run(event)
    ]
    stats = VerificationStats(
        self_test_n=len(self_test_indices),
        event_n=len(paired),
        estimated_tokens=_estimate_tokens(paired),
    )
    if not self_test_indices:
        # No verification transcript to compress. Do not TOKEN_STUB source
        # reads, repo evidence, or submission inspection to fit the window.
        return paired, stats

    keep_full = _keep_full_indices(paired, self_test_indices)
    ledger_entries = _build_ledger(paired, self_test_indices, ledger_cap=ledger_cap)
    ledger_body = _format_ledger(ledger_entries)
    ledger_host = next(
        (index for index in self_test_indices if index not in keep_full),
        None,
    )

    out = list(paired)
    stubbed = 0
    for index in self_test_indices:
        if index in keep_full:
            continue
        if index == ledger_host and ledger_body:
            out[index] = replace(out[index], body=ledger_body)
            continue
        out[index] = replace(out[index], body=RECORDED_STUB)
        stubbed += 1

    protected = set(keep_full)
    if ledger_host is not None:
        protected.add(ledger_host)

    overflow_masked = 0
    if trigger_tokens:
        out, overflow_masked = _overflow_mask(
            out,
            eligible=set(self_test_indices),
            protected=protected,
            trigger_tokens=trigger_tokens,
        )

    return out, VerificationStats(
        self_test_n=len(self_test_indices),
        kept_full=len(keep_full),
        ledger_lines=len(ledger_entries),
        stubbed=stubbed,
        overflow_masked=overflow_masked,
        event_n=len(out),
        estimated_tokens=_estimate_tokens(out),
    )


def first_exception_type(text: str) -> str | None:
    match = EXCEPTION_RE.search(text or "")
    if not match:
        return None
    return match.group(1)


def is_verification_failure(event: CondenserEvent) -> bool:
    if event.exit_code not in (None, 0):
        return True
    body = event.body or ""
    for amount, kind in PYTEST_COUNT_RE.findall(body):
        key = kind.lower()
        if key.startswith(("fail", "error")) and int(amount) > 0:
            return True
    return first_exception_type(body) is not None


def ledger_line_for(event: CondenserEvent) -> str:
    skeleton = command_skeleton(event.command or "") or "(unknown command)"
    if len(skeleton) > 120:
        skeleton = skeleton[:117] + "..."
    body = event.body or ""
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for amount, kind in PYTEST_COUNT_RE.findall(body):
        key = "error" if kind.lower().startswith("error") else kind.lower()
        if key in counts:
            counts[key] = int(amount)
    pytest_like = any(counts.values()) or "=====" in body
    if pytest_like:
        parts = []
        if counts["passed"]:
            parts.append(f"{counts['passed']} passed")
        if counts["failed"]:
            parts.append(f"{counts['failed']} failed")
        if counts["error"]:
            parts.append(f"{counts['error']} error")
        if counts["skipped"]:
            parts.append(f"{counts['skipped']} skipped")
        detail = ", ".join(parts) if parts else outcome_fingerprint(body, event.exit_code)
        return f"{skeleton}: {detail}"
    bits = [f"exit={event.exit_code if event.exit_code is not None else '?'}"]
    exc = first_exception_type(body)
    if exc:
        bits.append(exc)
    return f"{skeleton}: {' '.join(bits)}"


def _pair_preceding_commands(events: list[CondenserEvent]) -> list[CondenserEvent]:
    out: list[CondenserEvent] = []
    last_command: str | None = None
    last_path: str | None = None
    for event in events:
        if not event.is_observation:
            last_command = event.command
            last_path = event.path
            out.append(event)
            continue
        if event.command:
            out.append(event)
            continue
        if last_command:
            out.append(
                replace(
                    event,
                    command=last_command,
                    path=event.path or last_path,
                )
            )
            continue
        out.append(event)
    return out


def _is_self_test_run(event: CondenserEvent) -> bool:
    tool = (event.tool_name or "terminal").strip().lower() or "terminal"
    if tool in {"file_editor", "str_replace_editor", "edit_file"}:
        # Editor observations are not self-test *runs*.
        return False
    return (
        classify(tool, event.command or "", event.path or "", "")
        == "self_test_run"
    )


def _keep_full_indices(
    events: list[CondenserEvent],
    self_test_indices: list[int],
) -> set[int]:
    keep: set[int] = set()
    if not self_test_indices:
        return keep
    keep.add(self_test_indices[-1])
    for index in reversed(self_test_indices):
        if is_verification_failure(events[index]):
            keep.add(index)
            break
    return keep


def _build_ledger(
    events: list[CondenserEvent],
    self_test_indices: list[int],
    *,
    ledger_cap: int,
) -> OrderedDict[str, str]:
    ledger: OrderedDict[str, str] = OrderedDict()
    for index in self_test_indices:
        event = events[index]
        key = command_skeleton(event.command or "") or f"obs:{index}"
        if key in ledger:
            del ledger[key]
        ledger[key] = ledger_line_for(event)
        while len(ledger) > max(1, ledger_cap):
            ledger.popitem(last=False)
    return ledger


def _format_ledger(entries: OrderedDict[str, str]) -> str:
    if not entries:
        return ""
    lines = [LEDGER_HEADER]
    for value in entries.values():
        lines.append(f"- {value}")
    return "\n".join(lines)


def _estimate_tokens(events: Iterable[CondenserEvent]) -> int:
    return sum(len(event.body) for event in events) // OVERFLOW_CHARS_PER_TOKEN


def _overflow_mask(
    events: list[CondenserEvent],
    *,
    eligible: set[int],
    protected: set[int],
    trigger_tokens: int,
) -> tuple[list[CondenserEvent], int]:
    """TOKEN_STUB oldest leftover self-test bodies if still over budget.

    Never masks cat/grep source, repo evidence, or submission reads. If the
    window is still over after compressing verification observations, stop.
    """

    budget = max(1, int(trigger_tokens))
    total = _estimate_tokens(events)
    if total <= budget:
        return events, 0
    out = list(events)
    masked = 0
    for index in sorted(eligible):
        if total <= budget:
            break
        event = out[index]
        if not event.is_observation or index in protected:
            continue
        if event.path and _looks_like_spec_path(event.path):
            continue
        if event.body in {TOKEN_STUB, RECORDED_STUB} or event.body.startswith(
            LEDGER_HEADER
        ):
            continue
        reduction = max(0, len(event.body) - len(TOKEN_STUB)) // OVERFLOW_CHARS_PER_TOKEN
        out[index] = replace(event, body=TOKEN_STUB)
        total -= reduction
        masked += 1
    return out, masked
