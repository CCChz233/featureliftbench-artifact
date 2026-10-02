from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "harness/scripts/analyze_token_utility_phase0.py"
SPEC = importlib.util.spec_from_file_location("analyze_token_utility_phase0", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_naive_event_timestamp_aligns_with_audit_z() -> None:
    naive = MOD._parse_ts("2026-08-12T16:56:48.854985")
    zulu = MOD._parse_ts("2026-08-12T16:56:48Z")
    assert naive is not None and zulu is not None
    assert abs(naive - zulu) < 1.0
    expected = datetime(2026, 8, 12, 16, 56, 48, tzinfo=timezone.utc).timestamp()
    assert abs(zulu - expected) < 1.0


def test_tokens_at_matches_call_before_event() -> None:
    calls = [
        (100.0, 10, 10),
        (200.0, 20, 30),
        (300.0, 40, 70),
    ]
    assert MOD.tokens_at(calls, 200.4) == 30
    assert MOD.tokens_at(calls, 198.5) == 10
    assert MOD.tokens_at(calls, 50.0) == 0
