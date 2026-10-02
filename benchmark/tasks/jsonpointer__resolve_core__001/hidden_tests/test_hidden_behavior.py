from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from featurelifted import (
    EndOfList,
    JsonPointer,
    JsonPointerException,
    escape,
    resolve_pointer,
    set_pointer,
    unescape,
)


SPEC_DOC = {
    "foo": ["bar", "baz"],
    "": 0,
    "a/b": 1,
    "c%d": 2,
    "e^f": 3,
    "g|h": 4,
    "i\\j": 5,
    'k"l': 6,
    " ": 7,
    "m~n": 8,
}


def test_escape_round_trip_paths() -> None:
    paths = ["", "/foo", "/a~1b", "/m~0n", "/ "]
    for path in paths:
        ptr = JsonPointer(path)
        assert ptr.path == path
        rebuilt = JsonPointer.from_parts(ptr.get_parts())
        assert rebuilt == ptr
    assert escape("a/b~c") == "a~1b~0c"
    assert unescape("a~1b~0c") == "a/b~c"


def test_invalid_escape_raises() -> None:
    with pytest.raises(JsonPointerException):
        JsonPointer("/foo/bar~2")
    with pytest.raises(JsonPointerException):
        JsonPointer("/foo/bar~")


def test_end_of_list_marker() -> None:
    doc = {"foo": ["bar", "baz"]}
    result = resolve_pointer(doc, "/foo/-")
    assert isinstance(result, EndOfList)
    with pytest.raises(JsonPointerException):
        resolve_pointer(doc, "/foo/-/1")


def test_array_index_rejects_leading_zero() -> None:
    doc = [0, 1, 2]
    with pytest.raises(JsonPointerException):
        resolve_pointer(doc, "/01")


def test_set_append_via_dash() -> None:
    doc = {"foo": ["bar", "baz"]}
    set_pointer(doc, "/foo/-", "cod")
    assert resolve_pointer(doc, "/foo/2") == "cod"


def test_set_out_of_place_deepcopy() -> None:
    doc = copy.deepcopy(SPEC_DOC)
    original = copy.deepcopy(doc)
    newdoc = set_pointer(doc, "/foo/1", "cod", inplace=False)
    assert resolve_pointer(newdoc, "/foo/1") == "cod"
    assert resolve_pointer(doc, "/foo/1") == "baz"
    assert doc == original


def test_resolve_missing_with_default() -> None:
    assert resolve_pointer(SPEC_DOC, "/missing", None) is None
    assert resolve_pointer(SPEC_DOC, "/a%20b", None) is None


def test_pointer_join_operator() -> None:
    ptr1 = JsonPointer("/a/b/c")
    ptr2 = JsonPointer("/a/b")
    joined = ptr1 / ptr2
    assert joined.path == "/a/b/c/a/b"
    assert ptr2 in ptr1
    assert JsonPointer("/b/c") not in ptr1


def test_no_jsonpointer_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from jsonpointer|import jsonpointer)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
