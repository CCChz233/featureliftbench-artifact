"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Environment,
    nodes,
    lexer,
    parser,
)


def test_required_api_surface():
    assert isinstance(Environment, type)
    assert hasattr(Environment, 'parse')
    assert hasattr(Environment, 'lex')
    assert nodes is not None
    assert isinstance(getattr(nodes, 'For'), type)
    assert isinstance(getattr(nodes, 'If'), type)
    assert isinstance(getattr(nodes, 'Name'), type)
    assert isinstance(getattr(nodes, 'Output'), type)
    assert isinstance(getattr(nodes, 'Template'), type)
    assert lexer is not None
    assert isinstance(getattr(lexer, 'Lexer'), type)
    assert hasattr(getattr(lexer, 'Lexer'), 'tokenize')
    assert parser is not None
    assert isinstance(getattr(parser, 'Parser'), type)
    assert hasattr(getattr(parser, 'Parser'), 'parse')
