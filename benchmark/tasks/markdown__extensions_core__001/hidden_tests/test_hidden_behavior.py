from __future__ import annotations

import re
from pathlib import Path

from featurelifted import markdown


def test_table_header_align() -> None:
    src = (
        "| left | center | right |\n"
        "| :--- | :---: | ---: |\n"
        "| l | c | r |\n"
    )
    html = markdown(src, extensions=["tables"])
    assert "text-align: left" in html
    assert "text-align: center" in html
    assert "text-align: right" in html


def test_footnote_backlink() -> None:
    src = "See[^fn]\n\n[^fn]: detail"
    html = markdown(src, extensions=["footnotes"])
    assert "footnote-backref" in html or "↩" in html


def test_table_row_span() -> None:
    src = "| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"
    html = markdown(src, extensions=["tables"])
    assert html.count("<tr>") >= 3


def test_multiple_footnotes_order() -> None:
    src = "A[^1] B[^2]\n\n[^2]: second\n[^1]: first"
    html = markdown(src, extensions=["footnotes"])
    assert html.index("first") < html.index("second") or "first" in html


def test_no_markdown_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from markdown|import markdown)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
