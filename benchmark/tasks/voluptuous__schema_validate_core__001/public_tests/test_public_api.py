from __future__ import annotations

import pytest

from featurelifted import MultipleInvalid, Optional, Required, Schema


def test_schema_required_field() -> None:
    schema = Schema({Required("name"): str})
    assert schema({"name": "ada"}) == {"name": "ada"}
    with pytest.raises(MultipleInvalid):
        schema({})


def test_optional_missing_key() -> None:
    schema = Schema({Optional("note"): str})
    assert schema({}) == {}


def test_basic_type_validation() -> None:
    schema = Schema({"name": str, "age": int})
    assert schema({"name": "ada", "age": 3}) == {"name": "ada", "age": 3}
    with pytest.raises(MultipleInvalid):
        schema({"name": "ada", "age": "three"})
