from __future__ import annotations

from featurelifted import PythonLexer, get_lexer_by_name, lex
from featurelifted import token


def test_python_lexer_keywords_and_names() -> None:
    lexer = PythonLexer()
    kinds = [ttype for ttype, _ in lex("def greet(name):\n    return name", lexer)]

    assert token.Keyword in kinds
    assert token.Name.Function in kinds
    assert token.Name in kinds


def test_get_lexer_by_name_returns_python_lexer() -> None:
    lexer = get_lexer_by_name("python")

    assert lexer.name == "Python"
    assert list(lex("x = 1", lexer))
