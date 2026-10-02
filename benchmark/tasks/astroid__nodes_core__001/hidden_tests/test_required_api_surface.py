"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse,
    ClassDef,
    FunctionDef,
    AsyncFunctionDef,
    Match,
)


def test_required_api_surface():
    assert callable(parse)
    assert isinstance(ClassDef, type)
    assert isinstance(FunctionDef, type)
    assert isinstance(AsyncFunctionDef, type)
    assert isinstance(Match, type)
