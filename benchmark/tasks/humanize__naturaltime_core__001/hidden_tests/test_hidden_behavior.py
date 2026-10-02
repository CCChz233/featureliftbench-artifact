from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from featurelifted import naturalday, naturaldelta, naturaltime, precisedelta


def test_naturaltime_future_with_when() -> None:
    when = datetime(2020, 1, 15, 12, 0, 0)
    future = when + timedelta(hours=3)
    assert naturaltime(future, when=when) == "3 hours from now"


def test_precisedelta_suppress_days() -> None:
    delta = timedelta(days=2, seconds=33)
    assert precisedelta(delta, minimum_unit="minutes", suppress=["days"]) == "48 hours and 0.55 minutes"


def test_naturaldelta_long_month_granularity() -> None:
    assert naturaldelta(timedelta(days=400), months=True) == "1 year, 1 month"


def test_naturalday_today_label() -> None:
    assert naturalday(date.today()) == "today"


def test_naturaltime_two_hour_past() -> None:
    when = datetime(2020, 6, 1, 12, 0, 0)
    past = when - timedelta(hours=2)
    assert naturaltime(past, when=when) == "2 hours ago"


def test_no_humanize_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from humanize|import humanize)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
