from __future__ import annotations

from featurelifted import UTC, DateTime, Duration, datetime, duration, parse


def test_parse_iso_date() -> None:
    result = parse("2024-06-15")
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 15


def test_parse_iso_datetime_zulu() -> None:
    result = parse("2024-06-15T10:30:45Z")
    assert isinstance(result, DateTime)
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 15
    assert result.hour == 10
    assert result.minute == 30
    assert result.second == 45
    assert result.timezone_name == "UTC"


def test_datetime_format_tokens() -> None:
    dt = datetime(2024, 6, 15, 10, 30, 5, tz=UTC)
    assert dt.format("YYYY-MM-DD HH:mm:ss") == "2024-06-15 10:30:05"


def test_duration_constructor_and_total_seconds() -> None:
    d = duration(days=1, hours=2, minutes=30)
    assert isinstance(d, Duration)
    assert d.total_seconds() == 95400.0


def test_parse_iso_duration() -> None:
    result = parse("P1DT12H")
    assert isinstance(result, Duration)
    assert result.days == 1
    assert result.hours == 12
