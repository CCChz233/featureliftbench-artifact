
import pytest

from featurelifted import FakeElement, Selector, SelectorSyntaxError, extract_text


def test_xpath_with_namespace():
    Selector.register_namespace("x", "http://example.com")
    root = FakeElement("root", children=[FakeElement("item", text="one")])
    assert Selector(root).xpath("//x:item").getall() == ["one"]
    Selector.remove_namespace("x")


def test_extract_text_default():
    child = FakeElement("span", text="inner", tail="!")
    root = FakeElement("div", text="A", children=[child])
    assert extract_text([root]) == "Ainner!"


def test_empty_css_selector_raises():
    root = FakeElement("root")
    with pytest.raises(SelectorSyntaxError):
        Selector(root).css("   ")
