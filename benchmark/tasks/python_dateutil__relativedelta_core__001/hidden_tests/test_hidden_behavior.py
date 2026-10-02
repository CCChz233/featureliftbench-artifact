from __future__ import annotations

import datetime
import re
from pathlib import Path

import pytest

from featurelifted import FR, MO, relativedelta


def test_normalized_fractional_days() -> None:
    delta = relativedelta(days=1.5, hours=2)
    normalized = delta.normalized()
    assert normalized.days == 1
    assert normalized.hours == 14
    assert normalized.minutes == 0


def test_weekday_nth_first_monday() -> None:
    dt = datetime.datetime(2020, 4, 15)
    result = dt + relativedelta(day=1, weekday=MO(1))
    assert result == datetime.datetime(2020, 4, 6)
    assert result.weekday() == 0


def test_relativedelta_diff_months() -> None:
    dt1 = datetime.datetime(2020, 3, 15)
    dt2 = datetime.datetime(2020, 1, 10)
    delta = relativedelta(dt1, dt2)
    assert delta.months == 2
    assert delta.days == 5


def test_last_friday_of_month() -> None:
    dt = datetime.datetime(2020, 1, 1)
    result = dt + relativedelta(day=31, weekday=FR(-1))
    assert result == datetime.datetime(2020, 1, 31)
    assert result.weekday() == 4


def test_yearday_sets_month_day() -> None:
    delta = relativedelta(yearday=60)
    dt = datetime.datetime(2020, 1, 1)
    result = dt + delta
    assert result.month == 2
    assert result.day == 29


def test_leapdays_post_february() -> None:
    dt = datetime.datetime(2020, 2, 28)
    result = dt + relativedelta(months=1, leapdays=1)
    assert result == datetime.datetime(2020, 3, 29)


def test_subtract_relativedelta() -> None:
    dt = datetime.datetime(2020, 6, 15)
    result = dt - relativedelta(months=2, days=5)
    assert result == datetime.datetime(2020, 4, 10)


def test_no_dateutil_import_surface() -> None:
    import featurelifted

    forbidden = {"parser", "tz", "rrule", "zoneinfo"}
    exports = set(getattr(featurelifted, "__all__", []))
    for name in forbidden:
        assert name not in exports, f"unexpected export: {name}"

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from dateutil|import dateutil)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))


def test_non_integer_years_months_rejected() -> None:
    with pytest.raises(ValueError):
        relativedelta(years=1.5)
