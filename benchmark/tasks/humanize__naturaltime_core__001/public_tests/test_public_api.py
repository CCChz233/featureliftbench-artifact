from __future__ import annotations

from datetime import datetime, timedelta

from featurelifted import naturaldate, naturaldelta, naturaltime


def test_naturaltime_past_with_when() -> None:
    when = datetime(2020, 1, 15, 12, 0, 0)
    past = when - timedelta(minutes=30)
    assert naturaltime(past, when=when) == "30 minutes ago"


def test_naturaldelta_hours() -> None:
    assert naturaldelta(timedelta(hours=2, minutes=5)) == "2 hours"


def test_naturaldate_distant_year() -> None:
    assert naturaldate(datetime(2020, 1, 1)) == "Jan 01 2020"
