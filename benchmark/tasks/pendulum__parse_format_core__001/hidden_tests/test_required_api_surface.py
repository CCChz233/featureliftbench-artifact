"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    UTC,
    Date,
    DateTime,
    Duration,
    ParserError,
    Time,
    datetime,
    duration,
    fixed_timezone,
    parse,
)


def test_required_api_surface():
    assert UTC is not None
    assert isinstance(Date, type)
    assert Date is not None
    assert Date is not None
    assert Date is not None
    assert Date is not None
    assert Date is not None
    assert isinstance(DateTime, type)
    assert DateTime is not None
    assert DateTime is not None
    assert DateTime is not None
    assert DateTime is not None
    assert isinstance(Duration, type)
    assert Duration is not None
    assert hasattr(Duration, 'in_days')
    assert Duration is not None
    assert Duration is not None
    assert Duration is not None
    assert Duration is not None
    assert Duration is not None
    assert Duration is not None
    assert issubclass(ParserError, BaseException)
    assert isinstance(Time, type)
    assert datetime is not None
    assert duration is not None
    assert callable(fixed_timezone)
    assert callable(parse)
