from __future__ import annotations

import datetime

from featurelifted import MO, relativedelta


def test_add_months_to_datetime() -> None:
    dt = datetime.datetime(2020, 1, 15, 12, 0)
    result = dt + relativedelta(months=1)
    assert result == datetime.datetime(2020, 2, 15, 12, 0)


def test_add_days_and_hours() -> None:
    dt = datetime.datetime(2020, 1, 1)
    result = dt + relativedelta(days=2, hours=3)
    assert result == datetime.datetime(2020, 1, 3, 3, 0)


def test_weekday_constant_identity() -> None:
    assert MO.weekday == 0
    assert repr(MO(+2)) == "MO(+2)"


def test_absolute_day_replacement() -> None:
    dt = datetime.datetime(2020, 3, 20)
    result = dt + relativedelta(day=1)
    assert result == datetime.datetime(2020, 3, 1)
