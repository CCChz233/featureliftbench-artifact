
from datetime import datetime

from featurelifted import CronTrigger


def test_specific_minute_and_hour():
    trigger = CronTrigger(minute=15, hour=9)
    start = datetime(2024, 1, 1, 9, 7)
    nxt = trigger.get_next_fire_time(start)
    assert nxt == datetime(2024, 1, 1, 9, 15)
