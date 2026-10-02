
from featurelifted import FakeElement, Selector


def test_css_id_selector():
    root = FakeElement("root", children=[FakeElement("p", text="hi", attrib={"id": "main"})])
    assert Selector(root).css("#main").get() == "hi"
