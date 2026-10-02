"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    markdown,
    Markdown,
)


def test_required_api_surface():
    assert callable(markdown)
    assert isinstance(Markdown, type)
