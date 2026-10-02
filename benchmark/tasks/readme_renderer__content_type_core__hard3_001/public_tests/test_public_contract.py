
from featurelifted import render_readme


def test_render_markdown_content_type():
    html, warnings = render_readme("# Title", "text/markdown")
    assert "markdown" in html
    assert warnings == []
