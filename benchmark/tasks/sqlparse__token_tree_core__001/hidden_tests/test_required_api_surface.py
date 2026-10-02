"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse,
    parsestream,
    sql,
    tokens,
)


def test_required_api_surface():
    assert callable(parse)
    assert callable(parsestream)
    assert sql is not None
    assert isinstance(getattr(sql, 'Comparison'), type)
    assert isinstance(getattr(sql, 'Identifier'), type)
    assert isinstance(getattr(sql, 'Statement'), type)
    assert isinstance(getattr(sql, 'Where'), type)
    assert tokens is not None
    assert getattr(tokens, 'Keyword') is not None
    assert getattr(getattr(tokens, 'Keyword'), 'DML') is not None
