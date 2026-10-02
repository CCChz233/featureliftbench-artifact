"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse,
    exceptions,
)


def test_required_api_surface():
    assert callable(parse)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'JsonPathLexerError'), BaseException)
    assert issubclass(getattr(exceptions, 'JsonPathParserError'), BaseException)
