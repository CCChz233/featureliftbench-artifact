from __future__ import annotations

import pytest

from featurelifted import Draft202012Validator
from featurelifted import ValidationError
from featurelifted import validate


def test_validate_object_required_properties_and_minimum() -> None:
    schema = {
        "type": "object",
        "properties": {
            "age": {"type": "integer", "minimum": 0},
            "name": {"type": "string", "minLength": 2},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    validate({"name": "Ada", "age": 3}, schema)

    with pytest.raises(ValidationError) as excinfo:
        validate({"age": -1, "extra": True}, schema)

    assert excinfo.value.validator in {"required", "minimum", "additionalProperties"}


def test_iter_errors_exposes_paths_and_validity() -> None:
    validator = Draft202012Validator(
        {
            "type": "object",
            "properties": {"age": {"type": "integer", "minimum": 0}},
            "required": ["age"],
        }
    )

    errors = list(validator.iter_errors({"age": -1}))

    assert not validator.is_valid({"age": -1})
    assert validator.is_valid({"age": 1})
    assert len(errors) == 1
    assert list(errors[0].path) == ["age"]
    assert errors[0].validator == "minimum"
