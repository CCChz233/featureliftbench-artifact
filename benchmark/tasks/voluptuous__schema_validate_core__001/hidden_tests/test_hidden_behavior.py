from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import All, Any, Coerce, In, MultipleInvalid, Required, Schema


def test_nested_schema_validation() -> None:
    profile = Schema({Required("city"): str})
    user = Schema({Required("name"): str, Required("profile"): profile})
    result = user({"name": "Ada", "profile": {"city": "Paris"}})
    assert result["profile"]["city"] == "Paris"

    with pytest.raises(MultipleInvalid):
        user({"name": "Ada", "profile": {}})


def test_all_any_in_and_coerce() -> None:
    def non_negative(n: int) -> int:
        if n < 0:
            raise ValueError("must be non-negative")
        return n

    schema = Schema(
        {
            Required("mode"): Any("alpha", "beta"),
            Required("count"): All(Coerce(int), non_negative),
            Required("color"): In(["red", "blue"]),
        }
    )
    assert schema({"mode": "alpha", "count": "3", "color": "red"}) == {
        "mode": "alpha",
        "count": 3,
        "color": "red",
    }

    with pytest.raises(MultipleInvalid):
        schema({"mode": "gamma", "count": "3", "color": "red"})


def test_multiple_invalid_error_paths() -> None:
    item = Schema({Required("id"): int})
    schema = Schema({Required("items"): [item]})
    with pytest.raises(MultipleInvalid) as excinfo:
        schema({"items": [{"id": "nope"}]})
    err = excinfo.value
    assert len(err.errors) >= 1
    assert err.errors[0].path == ["items", 0, "id"]


def test_no_voluptuous_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from voluptuous|import voluptuous)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
