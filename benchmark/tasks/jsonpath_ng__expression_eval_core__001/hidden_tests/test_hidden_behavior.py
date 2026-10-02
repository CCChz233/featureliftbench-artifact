from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from featurelifted import parse
from featurelifted.exceptions import JsonPathLexerError, JsonPathParserError


def test_filter_expression_selects_items() -> None:
    data = {"items": [{"price": 5, "ok": True}, {"price": 15, "ok": True}]}
    matches = parse("$.items[?(@.price < 10)]").find(data)
    assert len(matches) == 1
    assert matches[0].value["price"] == 5


def test_bracket_slice_selects_range() -> None:
    data = {"nums": [10, 20, 30, 40]}
    matches = parse("$.nums[1:3]").find(data)
    assert [m.value for m in matches] == [20, 30]


def test_update_nested_path() -> None:
    data = {"store": {"book": [{"price": 1}, {"price": 2}]}}
    doc = copy.deepcopy(data)
    parse("$.store.book[1].price").update(doc, 99)
    assert doc["store"]["book"][1]["price"] == 99


def test_negative_index_selects_last() -> None:
    data = {"arr": ["a", "b", "c"]}
    matches = parse("$.arr[-1]").find(data)
    assert [m.value for m in matches] == ["c"]


def test_invalid_expression_raises() -> None:
    with pytest.raises((JsonPathLexerError, JsonPathParserError, Exception)):
        parse("$[???]").find({"x": 1})


def test_no_jsonpath_ng_import_surface() -> None:
    import featurelifted

    forbidden = {"bin"}
    exports = set(getattr(featurelifted, "__all__", []))
    for name in forbidden:
        assert name not in exports

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from jsonpath_ng|import jsonpath_ng)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
