from __future__ import annotations

from featurelifted.markup import escape, render
from featurelifted.text import Text


def test_render_escape_and_from_markup() -> None:
    assert escape("plain [bold]") == "plain \\[bold]"

    text = render("[bold]Hello[/bold] [link=https://example.com]World[/link]")
    assert text.plain == "Hello World"
    assert any("bold" in str(span.style).lower() for span in text.spans)

    via_text = Text.from_markup("[italic]x[/italic]")
    assert via_text.plain == "x"
