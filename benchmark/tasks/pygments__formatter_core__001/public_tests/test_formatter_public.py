from __future__ import annotations

from io import StringIO

from featurelifted import HtmlFormatter, get_lexer_by_name, highlight


def test_html_formatter_wraps_tokens() -> None:
    formatter = HtmlFormatter()
    lexer = get_lexer_by_name("python")
    output = StringIO()
    highlight("x = 1", lexer, formatter, output)
    html = output.getvalue()

    assert '<span class="' in html
    assert "x" in html
    assert "&lt;" not in html


def test_nowrap_option_omits_outer_div() -> None:
    formatter = HtmlFormatter(nowrap=True)
    lexer = get_lexer_by_name("python")
    html = highlight("pass", lexer, formatter)

    assert "<div" not in html
    assert "pass" in html
