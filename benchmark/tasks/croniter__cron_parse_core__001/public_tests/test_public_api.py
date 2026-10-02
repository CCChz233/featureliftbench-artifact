from __future__ import annotations

from datetime import datetime

from featurelifted import croniter


BASE = datetime(2024, 1, 15, 12, 0, 0)


def test_daily_noon_next() -> None:
    itr = croniter("0 12 * * *", BASE)
    assert itr.get_next(datetime) == datetime(2024, 1, 16, 12, 0, 0)


def test_daily_noon_prev() -> None:
    itr = croniter("0 12 * * *", BASE)
    assert itr.get_prev(datetime) == datetime(2024, 1, 14, 12, 0, 0)


def test_hourly_on_base_minute() -> None:
    itr = croniter("30 * * * *", BASE)
    assert itr.get_next(datetime) == datetime(2024, 1, 15, 12, 30, 0)


def test_weekday_field_parses() -> None:
    itr = croniter("0 9 * * 1", BASE)
    assert itr.get_next(datetime) == datetime(2024, 1, 22, 9, 0, 0)
