from __future__ import annotations

from featurelifted import get


def test_get_iso_datetime() -> None:
    a = get("2020-01-15T12:30:00+00:00")
    assert a.year == 2020
    assert a.month == 1
    assert a.day == 15
    assert a.hour == 12
    assert a.minute == 30


def test_format_basic_tokens() -> None:
    a = get("2020-01-15T12:30:00+00:00")
    assert a.format("YYYY-MM-DD HH:mm:ss ZZ") == "2020-01-15 12:30:00 +00:00"


def test_get_with_format_string() -> None:
    a = get("2020-01-15 12:30", "YYYY-MM-DD HH:mm")
    assert a.format("YYYY-MM-DD") == "2020-01-15"
