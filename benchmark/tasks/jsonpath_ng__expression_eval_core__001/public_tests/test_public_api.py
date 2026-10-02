from __future__ import annotations

import copy

from featurelifted import parse


def test_parse_find_simple_path() -> None:
    data = {"user": {"name": "ada"}}
    matches = parse("$.user.name").find(data)
    assert [m.value for m in matches] == ["ada"]


def test_wildcard_array_find() -> None:
    data = {"items": [{"id": 1}, {"id": 2}]}
    matches = parse("$.items[*].id").find(data)
    assert [m.value for m in matches] == [1, 2]


def test_update_value_in_place() -> None:
    data = {"count": 1}
    doc = copy.deepcopy(data)
    parse("$.count").update(doc, 9)
    assert doc["count"] == 9


def test_root_child_fields() -> None:
    data = {"a": 1, "b": 2}
    matches = parse("$.*").find(data)
    assert sorted(m.value for m in matches) == [1, 2]
