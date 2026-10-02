from __future__ import annotations

from featurelifted import parse, unparse


def test_simple_parse_text_node() -> None:
    assert parse("<a>data</a>") == {"a": "data"}


def test_parse_attributes_default_prefix() -> None:
    assert parse('<a href="xyz"/>') == {"a": {"@href": "xyz"}}


def test_parse_repeated_siblings_become_list() -> None:
    xml = "<a><b>1</b><b>2</b><b>3</b></a>"
    assert parse(xml) == {"a": {"b": ["1", "2", "3"]}}


def test_unparse_simple_element() -> None:
    xml = unparse({"greeting": "hello"})
    assert "<greeting>hello</greeting>" in xml


def test_roundtrip_simple_document() -> None:
    original = {"note": {"@id": "1", "#text": "hi"}}
    reparsed = parse(unparse(original))
    assert reparsed == original
