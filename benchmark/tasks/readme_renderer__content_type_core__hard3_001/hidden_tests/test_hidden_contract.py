
from featurelifted import render_readme


def test_unknown_media_type_falls_back_to_plain():
    html, warnings = render_readme("hello", "text/x-custom")
    assert "hello" in html
    assert any("Unknown content type" in item for item in warnings)


def test_plain_text_renders_with_line_breaks():
    html, _ = render_readme("line1\nline2", "text/plain")
    assert "<br" in html


def test_unknown_charset_warns():
    _, warnings = render_readme("x", "text/plain; charset=iso-8859-1")
    assert any("charset" in item for item in warnings)
