from __future__ import annotations

from featurelifted.zpt.template import PageTemplate


def test_render_tal_content() -> None:
    template = PageTemplate("<div tal:content='name'>placeholder</div>")
    assert template.render(name="Ada").strip() == "<div>Ada</div>"


def test_render_python_expression() -> None:
    template = PageTemplate("<span>${name.upper()}</span>")
    assert "ADA" in template.render(name="ada")
