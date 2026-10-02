
from datetime import datetime

from featurelifted import CronTrigger


def test_end_time_boundary():
    end = datetime(2024, 1, 1, 10, 0)
    trigger = CronTrigger(minute=0, hour=9, end_time=end)
    now = datetime(2024, 1, 1, 9, 30)
    assert trigger.get_next_fire_time(now) is None


def test_specific_day_and_hour():
    trigger = CronTrigger(day=1, hour=12, minute=30)
    now = datetime(2024, 1, 1, 12, 0)
    nxt = trigger.get_next_fire_time(now)
    assert nxt == datetime(2024, 1, 1, 12, 30)
