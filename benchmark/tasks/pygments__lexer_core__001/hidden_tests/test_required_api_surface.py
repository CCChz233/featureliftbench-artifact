"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    lex,
    get_lexer_by_name,
    PythonLexer,
    token,
)


def test_required_api_surface():
    assert callable(lex)
    assert callable(get_lexer_by_name)
    assert isinstance(PythonLexer, type)
    assert token is not None
    assert getattr(token, 'Comment') is not None
    assert getattr(token, 'Keyword') is not None
    assert getattr(token, 'Literal') is not None
    assert getattr(token, 'Name') is not None
    assert getattr(token, 'Number') is not None
    assert getattr(token, 'Operator') is not None
    assert getattr(token, 'String') is not None
    assert getattr(token, 'Text') is not None
    assert getattr(getattr(token, 'Comment'), 'Single') is not None
    assert getattr(getattr(token, 'Literal'), 'String') is not None
    assert getattr(getattr(token, 'Name'), 'Function') is not None
    assert getattr(getattr(token, 'Number'), 'Integer') is not None
    assert getattr(getattr(token, 'String'), 'Double') is not None
    assert getattr(getattr(getattr(token, 'Literal'), 'String'), 'Single') is not None
