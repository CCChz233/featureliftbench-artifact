from __future__ import annotations

from featurelifted import markdown


def test_simple_table() -> None:
    src = "| h1 | h2 |\n| --- | --- |\n| a | b |\n"
    html = markdown(src, extensions=["tables"])
    assert "<table>" in html
    assert "<th>h1</th>" in html
    assert "<td>a</td>" in html


def test_basic_footnote() -> None:
    src = "Text[^1]\n\n[^1]: note"
    html = markdown(src, extensions=["footnotes"])
    assert 'class="footnote"' in html or "footnote" in html
    assert "note" in html
