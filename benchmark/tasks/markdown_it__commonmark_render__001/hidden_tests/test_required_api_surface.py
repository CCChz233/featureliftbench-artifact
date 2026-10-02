"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    MarkdownIt,
)


def test_required_api_surface():
    assert isinstance(MarkdownIt, type)
    assert hasattr(MarkdownIt, 'render')
    assert hasattr(MarkdownIt, 'disable')
    assert hasattr(MarkdownIt, 'enable')
    assert hasattr(MarkdownIt, 'parse')
