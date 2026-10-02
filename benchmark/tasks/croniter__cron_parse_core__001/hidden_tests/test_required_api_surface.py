"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    croniter,
    datetime_to_timestamp,
    CroniterBadCronError,
    CroniterBadDateError,
    CroniterNotAlphaError,
)


def test_required_api_surface():
    assert callable(croniter)
    assert callable(datetime_to_timestamp)
    assert issubclass(CroniterBadCronError, BaseException)
    assert issubclass(CroniterBadDateError, BaseException)
    assert issubclass(CroniterNotAlphaError, BaseException)
