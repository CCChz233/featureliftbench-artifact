"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Lark,
    exceptions,
    load_grammar,
)


def test_required_api_surface():
    assert isinstance(Lark, type)
    assert hasattr(Lark, 'open')
    assert hasattr(Lark, 'parse')
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'GrammarError'), BaseException)
    assert load_grammar is not None
    assert isinstance(getattr(load_grammar, 'FromPackageLoader'), type)
