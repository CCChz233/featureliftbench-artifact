from __future__ import annotations

import pytest

from featurelifted import TemplateError
from featurelifted.zpt.template import PageTemplate


def test_tal_repeat_and_condition() -> None:
    src = """
    <ul>
      <li tal:repeat="item items" tal:content="item"></li>
    </ul>
    """
    out = PageTemplate(src).render(items=["a", "b"])
    assert out.count("<li>") == 2
    assert "a" in out and "b" in out


def test_tal_attributes_replace() -> None:
    src = '<a href="/old" tal:attributes="href link">link</a>'
    out = PageTemplate(src).render(link="/new")
    assert 'href="/new"' in out


def test_tal_replace_marker() -> None:
    src = '<span tal:replace="structure item">x</span>'
    out = PageTemplate(src).render(item="<b>hi</b>")
    assert "<b>hi</b>" in out
