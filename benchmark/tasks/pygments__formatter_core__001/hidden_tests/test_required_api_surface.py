"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    highlight,
    HtmlFormatter,
    get_lexer_by_name,
)


def test_required_api_surface():
    assert callable(highlight)
    assert isinstance(HtmlFormatter, type)
    assert callable(get_lexer_by_name)
