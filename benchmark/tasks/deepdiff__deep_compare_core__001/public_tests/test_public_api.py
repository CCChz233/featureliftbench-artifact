from __future__ import annotations

from featurelifted import DeepDiff


def test_shallow_dict_diff() -> None:
    d1 = {"a": 1, "b": 2}
    d2 = {"a": 1, "b": 3}
    diff = DeepDiff(d1, d2)
    assert "values_changed" in diff
    assert diff["values_changed"]["root['b']"]["new_value"] == 3


def test_identical_nested() -> None:
    d1 = {"x": {"y": [1, 2]}}
    d2 = {"x": {"y": [1, 2]}}
    assert DeepDiff(d1, d2) == {}
