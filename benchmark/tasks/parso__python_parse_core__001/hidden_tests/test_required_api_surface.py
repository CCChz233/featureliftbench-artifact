"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse,
    load_grammar,
    Grammar,
)


def test_required_api_surface():
    assert callable(parse)
    assert callable(load_grammar)
    assert isinstance(Grammar, type)
