from __future__ import annotations

import datetime

from featurelifted import DAILY, MONTHLY, WEEKLY, MO, rrule, rrulestr


def test_monthly_rrule_yields_dates() -> None:
    start = datetime.datetime(2020, 1, 15)
    rule = rrule(MONTHLY, dtstart=start, count=3)
    assert list(rule) == [
        datetime.datetime(2020, 1, 15),
        datetime.datetime(2020, 2, 15),
        datetime.datetime(2020, 3, 15),
    ]


def test_weekly_byweekday_filter() -> None:
    start = datetime.datetime(2020, 1, 6)  # Monday
    rule = rrule(WEEKLY, dtstart=start, byweekday=MO, count=2)
    assert list(rule) == [
        datetime.datetime(2020, 1, 6),
        datetime.datetime(2020, 1, 13),
    ]


def test_count_stops_iteration() -> None:
    start = datetime.datetime(2020, 1, 1)
    rule = rrule(DAILY, dtstart=start, count=2)
    assert len(list(rule)) == 2


def test_rrulestr_parses_monthly_rule() -> None:
    start = datetime.datetime(2020, 1, 15)
    rule = rrulestr("RRULE:FREQ=MONTHLY;COUNT=2", dtstart=start, ignoretz=True)
    assert list(rule) == [
        datetime.datetime(2020, 1, 15),
        datetime.datetime(2020, 2, 15),
    ]
