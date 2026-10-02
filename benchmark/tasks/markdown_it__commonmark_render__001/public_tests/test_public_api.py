from __future__ import annotations

from featurelifted import MarkdownIt


def test_commonmark_basic_html_rendering() -> None:
    markdown = MarkdownIt("commonmark")

    assert markdown.render("# Title").strip() == "<h1>Title</h1>"
    assert markdown.render("- a\n- b").strip() == "<ul>\n<li>a</li>\n<li>b</li>\n</ul>"
    assert markdown.render("[x](https://example.com)").strip() == (
        '<p><a href="https://example.com">x</a></p>'
    )


def test_parse_returns_useful_tokens() -> None:
    tokens = MarkdownIt("commonmark").parse("Hello **world**")

    assert tokens[0].type == "paragraph_open"
    assert tokens[1].type == "inline"
    assert tokens[1].children is not None
    assert [child.type for child in tokens[1].children] == [
        "text",
        "strong_open",
        "text",
        "strong_close",
        "text",
    ]
