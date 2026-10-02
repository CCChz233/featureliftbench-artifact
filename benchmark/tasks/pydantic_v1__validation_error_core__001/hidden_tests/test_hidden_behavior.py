from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import BaseModel, Extra, ValidationError, root_validator, validator


class LineItem(BaseModel):
    name: str
    qty: int


class Order(BaseModel):
    items: list[LineItem]


def test_nested_validation_error_loc_paths() -> None:
    with pytest.raises(ValidationError) as exc:
        Order(items=[{"name": "widget", "qty": "nope"}])
    errors = exc.value.errors()
    assert any(err["loc"] == ("items", 0, "qty") for err in errors)
    assert any(err["type"] == "type_error.integer" for err in errors)


class StrictPayload(BaseModel):
    x: int

    class Config:
        extra = Extra.forbid


def test_extra_forbid_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError) as exc:
        StrictPayload(x=1, surprise=True)
    errors = exc.value.errors()
    assert any(err["type"] == "value_error.extra" for err in errors)


class RangeModel(BaseModel):
    low: int
    high: int

    @root_validator
    def low_not_above_high(cls, values: dict) -> dict:
        if values.get("low", 0) > values.get("high", 0):
            raise ValueError("low must be <= high")
        return values


def test_root_validator_rejects_invalid_combo() -> None:
    with pytest.raises(ValidationError) as exc:
        RangeModel(low=10, high=3)
    errors = exc.value.errors()
    assert any(err["loc"] == ("__root__",) for err in errors)
    assert any(err["type"] == "value_error" for err in errors)


class ParsedNumber(BaseModel):
    value: int

    @validator("value", pre=True)
    def parse_digits(cls, v):  # noqa: ANN001
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v


def test_validator_pre_runs_before_type_check() -> None:
    model = ParsedNumber(value="42")
    assert model.value == 42


def test_multiple_errors_collected() -> None:
    class Multi(BaseModel):
        name: str
        age: int
        email: str

    with pytest.raises(ValidationError) as exc:
        Multi(name={}, age="x", email=[])
    assert len(exc.value.errors()) >= 2


def test_no_pydantic_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from pydantic|import pydantic)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
