from __future__ import annotations

from featurelifted import MarkdownIt


def test_nested_blocks_code_escaping_and_images() -> None:
    markdown = MarkdownIt("commonmark")

    assert markdown.render("> quote\n>\n> - item\n").strip() == (
        "<blockquote>\n<p>quote</p>\n<ul>\n<li>item</li>\n</ul>\n</blockquote>"
    )
    assert markdown.render("1. one\n2. two\n").strip() == (
        "<ol>\n<li>one</li>\n<li>two</li>\n</ol>"
    )
    assert markdown.render("`code & <tag>`").strip() == (
        "<p><code>code &amp; &lt;tag&gt;</code></p>"
    )
    assert markdown.render('![alt](img.png "title")').strip() == (
        '<p><img src="img.png" alt="alt" title="title" /></p>'
    )


def test_fence_rule_disable_and_link_attributes() -> None:
    markdown = MarkdownIt("commonmark")
    rendered = markdown.render("```python\nprint('x')\n```\n").strip()
    assert rendered == '<pre><code class="language-python">print(\'x\')\n</code></pre>'

    without_fence = MarkdownIt("commonmark").disable("fence")
    assert without_fence.render("```python\nx\n```").strip() == "<p><code>python x </code></p>"

    token = MarkdownIt("commonmark").parse("[site](https://example.com)")[1]
    assert token.children is not None
    link_open = token.children[0]
    assert link_open.type == "link_open"
    assert link_open.attrGet("href") == "https://example.com"


def test_strikethrough_and_reference_links() -> None:
    md = MarkdownIt("commonmark", {"linkify": False}).enable("strikethrough")
    html = md.render("~~gone~~ and [ref][]\n\n[ref]: https://example.com").strip()
    assert "<s>gone</s>" in html
    assert 'href="https://example.com"' in html
