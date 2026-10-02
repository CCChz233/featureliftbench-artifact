"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Lark,
    Tree,
    Token,
    UnexpectedToken,
    UnexpectedCharacters,
)


def test_required_api_surface():
    assert isinstance(Lark, type)
    assert hasattr(Lark, 'parse')
    assert isinstance(Tree, type)
    assert isinstance(Token, type)
    assert issubclass(UnexpectedToken, BaseException)
    assert issubclass(UnexpectedCharacters, BaseException)
