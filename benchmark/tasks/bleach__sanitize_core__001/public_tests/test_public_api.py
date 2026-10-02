from __future__ import annotations

from featurelifted import clean


def test_clean_strips_script() -> None:
    dirty = '<b>ok</b><script>alert(1)</script>'
    assert clean(dirty) == "<b>ok</b>&lt;script&gt;alert(1)&lt;/script&gt;"


def test_clean_allows_safe_link() -> None:
    dirty = '<a href="https://example.com" title="x">link</a>'
    out = clean(dirty)
    assert 'href="https://example.com"' in out
    assert "link" in out


def test_clean_escapes_unknown_tags() -> None:
    dirty = "<custom>text</custom>"
    assert clean(dirty) == "&lt;custom&gt;text&lt;/custom&gt;"
