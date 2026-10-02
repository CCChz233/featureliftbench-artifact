"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse,
    unparse,
    ParsingInterrupted,
)


def test_required_api_surface():
    assert parse is not None
    assert unparse is not None
    assert issubclass(ParsingInterrupted, BaseException)
