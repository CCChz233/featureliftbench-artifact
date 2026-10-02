from __future__ import annotations

from featurelifted import HtmlFormatter, get_lexer_by_name, highlight


def test_linenos_and_cssclass_options() -> None:
    formatter = HtmlFormatter(linenos=True, cssclass="source")
    lexer = get_lexer_by_name("python")
    html = highlight("a = 1\nb = 2", lexer, formatter)

    assert 'class="source"' in html
    assert "linenos" in html or "1" in html
    assert "a" in html and "b" in html


def test_html_escapes_angle_brackets_in_source() -> None:
    formatter = HtmlFormatter(nowrap=True)
    lexer = get_lexer_by_name("python")
    html = highlight("data = '<tag>'", lexer, formatter)

    assert "&lt;tag&gt;" in html


def test_full_document_and_keyword_highlighting() -> None:
    formatter = HtmlFormatter(full=True, title="snippet.py")
    lexer = get_lexer_by_name("python")
    html = highlight("def run():\n    return None", lexer, formatter)

    assert "snippet.py" in html
    assert "def" in html
    assert "run" in html
