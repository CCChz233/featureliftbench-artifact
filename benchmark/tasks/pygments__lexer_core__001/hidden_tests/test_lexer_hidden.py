from __future__ import annotations

from featurelifted import PythonLexer, lex
from featurelifted import token


def test_string_and_comment_tokens_are_distinct() -> None:
    lexer = PythonLexer()
    pairs = list(lex("# comment\nvalue = 'abc'", lexer))
    types = [ttype for ttype, _ in pairs]
    values = [value for _, value in pairs]

    assert token.Comment.Single in types
    assert token.Literal.String.Single in types
    assert "abc" in values


def test_stripall_option_removes_whitespace_tokens() -> None:
    lexer = PythonLexer(stripall=True)
    pairs = list(lex("  x  =  1  ", lexer))

    assert all(ttype is not token.Text for ttype, _ in pairs)
    assert [value for _, value in pairs if value.strip()] == ["x", "=", "1"]


def test_triple_quoted_string_and_operator_tokens() -> None:
    lexer = PythonLexer()
    pairs = list(lex('msg = """line\nmore"""\nresult = 1 + 2', lexer))
    types = [ttype for ttype, _ in pairs]

    assert token.String.Double in types
    assert token.Operator in types
    assert token.Number.Integer in types
