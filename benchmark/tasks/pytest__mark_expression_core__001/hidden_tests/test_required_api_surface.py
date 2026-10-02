"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Expression,
    ParseError,
    expression,
)


def test_required_api_surface():
    assert isinstance(Expression, type)
    assert hasattr(Expression, 'compile')
    assert hasattr(Expression, 'evaluate')
    assert issubclass(ParseError, BaseException)
    assert expression is not None
    assert isinstance(getattr(expression, 'Scanner'), type)
    assert getattr(expression, 'Scanner') is not None
    assert isinstance(getattr(expression, 'TokenType'), type)
    assert getattr(expression, 'TokenType') is not None
