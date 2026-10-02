"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    CronTrigger,
)


def test_required_api_surface():
    assert isinstance(CronTrigger, type)
    assert hasattr(CronTrigger, 'get_next_fire_time')
