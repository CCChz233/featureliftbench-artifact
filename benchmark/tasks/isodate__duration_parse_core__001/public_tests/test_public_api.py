from __future__ import annotations

from datetime import timedelta

from featurelifted import Duration, duration_isoformat, parse_duration


def test_parse_duration_days_hours() -> None:
    result = parse_duration("P1DT12H")
    assert isinstance(result, timedelta)
    assert result == timedelta(days=1, hours=12)


def test_parse_duration_weeks() -> None:
    result = parse_duration("P2W")
    assert result == timedelta(weeks=2)


def test_duration_isoformat() -> None:
    assert duration_isoformat(Duration(years=1, months=2, days=3)) == "P1Y2M3D"
