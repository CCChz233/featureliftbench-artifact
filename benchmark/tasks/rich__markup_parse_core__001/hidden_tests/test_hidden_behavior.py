from __future__ import annotations

import pytest

from featurelifted.errors import MarkupError
from featurelifted.markup import render
from featurelifted.text import Text


def test_nested_styles_and_implicit_close() -> None:
    text = render("[bold]A[italic]B[/]C[/bold]")
    assert text.plain == "ABC"
    styles = [str(span.style) for span in text.spans]
    assert any("bold" in s.lower() for s in styles)
    assert any("italic" in s.lower() for s in styles)


def test_markup_errors_and_escaped_brackets() -> None:
    with pytest.raises(MarkupError):
        render("[bold]x[/italic]")

    with pytest.raises(MarkupError):
        render("[/italic]orphan")

    text = render("literal \\[bold] kept")
    assert "[bold]" in text.plain


def test_meta_link_handler_and_repr() -> None:
    text = render("[link=https://example.com/a?q=1]Docs[/link]")
    assert text.plain == "Docs"
    assert text.spans
    roundtrip = Text.from_markup(text.markup)
    assert roundtrip.plain == "Docs"
