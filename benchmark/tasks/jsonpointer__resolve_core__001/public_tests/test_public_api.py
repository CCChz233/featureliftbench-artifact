from __future__ import annotations

from featurelifted import JsonPointer, resolve_pointer, set_pointer


DOC = {
    "foo": {
        "anArray": [{"prop": 44}],
        "another prop": {"baz": "A string"},
    }
}


def test_resolve_root_empty_pointer() -> None:
    assert resolve_pointer(DOC, "") is DOC


def test_resolve_nested_dict_path() -> None:
    assert resolve_pointer(DOC, "/foo/another prop/baz") == "A string"


def test_resolve_array_index() -> None:
    assert resolve_pointer(DOC, "/foo/anArray/0/prop") == 44


def test_set_pointer_inplace() -> None:
    doc = {"foo": {"items": [1, 2]}}
    set_pointer(doc, "/foo/items/1", 99)
    assert resolve_pointer(doc, "/foo/items/1") == 99


def test_json_pointer_path_round_trip() -> None:
    ptr = JsonPointer("/foo/0")
    assert ptr.path == "/foo/0"
    assert ptr.get_parts() == ["foo", "0"]
