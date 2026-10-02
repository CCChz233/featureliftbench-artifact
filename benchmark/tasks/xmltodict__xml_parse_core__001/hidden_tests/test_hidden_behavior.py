from __future__ import annotations

import re
from pathlib import Path

from featurelifted import parse, unparse


def test_namespace_collapse_map() -> None:
    xml = """
    <root xmlns="http://defaultns.com/"
          xmlns:a="http://a.com/"
          version="1.00">
      <x a:attr="val">1</x>
      <a:y>2</a:y>
    </root>
    """
    namespaces = {
        "http://defaultns.com/": "",
        "http://a.com/": "ns_a",
    }
    expected = {
        "root": {
            "@version": "1.00",
            "@xmlns": {
                "": "http://defaultns.com/",
                "a": "http://a.com/",
            },
            "x": {
                "@ns_a:attr": "val",
                "#text": "1",
            },
            "ns_a:y": "2",
        }
    }
    assert parse(xml, process_namespaces=True, namespaces=namespaces) == expected


def test_custom_attr_prefix_parse() -> None:
    assert parse('<a href="xyz"/>', attr_prefix="!") == {"a": {"!href": "xyz"}}


def test_semi_structured_mixed_content() -> None:
    xml = "<a>abc<b/>def</a>"
    assert parse(xml) == {"a": {"b": None, "#text": "abcdef"}}


def test_unparse_custom_attr_prefix_roundtrip() -> None:
    doc = {"item": {"!kind": "book", "#text": "title"}}
    xml = unparse(doc, attr_prefix="!")
    assert 'kind="book"' in xml
    assert parse(xml, attr_prefix="!") == doc


def test_force_cdata_wraps_text_nodes() -> None:
    assert parse("<a>data</a>", force_cdata=True) == {"a": {"#text": "data"}}


def test_no_xmltodict_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from xmltodict|import xmltodict)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
