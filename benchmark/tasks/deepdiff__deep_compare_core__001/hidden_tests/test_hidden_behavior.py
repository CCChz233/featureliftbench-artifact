from __future__ import annotations

import re
from pathlib import Path

from featurelifted import DeepDiff, extract, parse_path


def test_nested_dict_change() -> None:
    d1 = {"outer": {"inner": 1}}
    d2 = {"outer": {"inner": 2}}
    diff = DeepDiff(d1, d2)
    assert "root['outer']['inner']" in diff.get("values_changed", {})


def test_exclude_paths_wildcard() -> None:
    d1 = {"a": {"secret": 1, "keep": 1}, "b": 2}
    d2 = {"a": {"secret": 9, "keep": 1}, "b": 3}
    diff = DeepDiff(d1, d2, exclude_paths=["root['a']['secret']"])
    assert "root['b']" in diff.get("values_changed", {})
    assert "root['a']['secret']" not in diff.get("values_changed", {})


def test_list_item_added() -> None:
    d1 = {"items": [1, 2]}
    d2 = {"items": [1, 2, 3]}
    diff = DeepDiff(d1, d2)
    assert "iterable_item_added" in diff


def test_parse_path_and_extract() -> None:
    obj = {"users": [{"name": "ada"}, {"name": "bob"}]}
    elements = parse_path("root['users'][0]['name']")
    assert elements
    assert extract(obj, "root['users'][0]['name']") == "ada"


def test_no_deepdiff_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from deepdiff|import deepdiff)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
