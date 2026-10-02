from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import DateTime, Duration, ParserError, UTC, datetime, duration, parse


def test_parse_iso_week_calendar_date() -> None:
    result = parse("2016-W05-5")
    assert result.year == 2016
    assert result.month == 2
    assert result.day == 5


def test_parse_duration_weeks_component() -> None:
    result = parse("P2W")
    assert isinstance(result, Duration)
    assert result.weeks == 2
    assert result.remaining_days == 0
    assert result.in_days() == 14


def test_parse_duration_full_components() -> None:
    result = parse("P1Y2M3DT4H5M6S")
    assert isinstance(result, Duration)
    assert result.years == 1
    assert result.months == 2
    assert result.remaining_days == 3
    assert result.hours == 4
    assert result.minutes == 5
    assert result.remaining_seconds == 6


def test_format_literal_brackets() -> None:
    dt = datetime(2024, 3, 7, 8, 9, 10, tz=UTC)
    assert dt.format("YYYY [MM] DD") == "2024 MM 07"


def test_parse_fixed_offset_without_colon() -> None:
    result = parse("2024-06-15T10:30:00+0530")
    assert isinstance(result, DateTime)
    assert result.hour == 10
    assert result.minute == 30
    assert result.offset == 5 * 3600 + 30 * 60


def test_parse_common_day_first() -> None:
    result = parse("2024/15/06 08:15", day_first=True)
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 15
    assert result.hour == 8
    assert result.minute == 15


def test_parse_subsecond_truncation() -> None:
    result = parse("2024-06-15T10:30:00.123456789Z")
    assert isinstance(result, DateTime)
    assert result.microsecond == 123456


def test_duration_years_months_not_float() -> None:
    with pytest.raises(ValueError):
        duration(years=1.5)


def test_parse_invalid_iso_raises() -> None:
    with pytest.raises(ParserError):
        parse("not-a-datetime")


def test_no_pendulum_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from pendulum|import pendulum)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
