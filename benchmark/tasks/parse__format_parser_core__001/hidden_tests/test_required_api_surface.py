"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Parser,
    Result,
    compile,
    parse,
)


def test_required_api_surface():
    assert isinstance(Parser, type)
    assert isinstance(Result, type)
    assert callable(compile)
    assert callable(parse)
