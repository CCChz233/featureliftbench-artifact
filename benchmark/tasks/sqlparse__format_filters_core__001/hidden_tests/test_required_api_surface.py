"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    format,
    exceptions,
)


def test_required_api_surface():
    assert callable(format)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'SQLParseError'), BaseException)
