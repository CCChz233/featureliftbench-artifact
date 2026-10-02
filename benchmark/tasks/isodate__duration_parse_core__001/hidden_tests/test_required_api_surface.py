"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Duration,
    ISO8601Error,
    duration_isoformat,
    parse_duration,
    isodates,
)


def test_required_api_surface():
    assert isinstance(Duration, type)
    assert Duration is not None
    assert Duration is not None
    assert hasattr(Duration, 'totimedelta')
    assert Duration is not None
    assert issubclass(ISO8601Error, BaseException)
    assert callable(duration_isoformat)
    assert callable(parse_duration)
    assert isodates is not None
    assert callable(getattr(isodates, 'parse_date'))
