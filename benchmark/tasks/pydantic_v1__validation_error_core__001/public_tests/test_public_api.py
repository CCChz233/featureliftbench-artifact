from __future__ import annotations

import pytest

from featurelifted import BaseModel, Field, ValidationError, validator


class User(BaseModel):
    name: str
    age: int


def test_simple_model_parses_fields() -> None:
    user = User(name="ada", age=30)
    assert user.name == "ada"
    assert user.age == 30


def test_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        User(name="ada")
    errors = exc.value.errors()
    assert len(errors) >= 1
    assert errors[0]["loc"] == ("age",)
    assert "type" in errors[0]


class Product(BaseModel):
    sku: str

    @validator("sku")
    def uppercase_sku(cls, value: str) -> str:
        return value.upper()


def test_field_validator_runs() -> None:
    product = Product(sku="ab12")
    assert product.sku == "AB12"


def test_parse_obj_classmethod() -> None:
    user = User.parse_obj({"name": "bob", "age": 21})
    assert user.age == 21
