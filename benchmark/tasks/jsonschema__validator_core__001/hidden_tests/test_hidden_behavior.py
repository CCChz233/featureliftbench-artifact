from __future__ import annotations

import pytest

from featurelifted import Draft202012Validator
from featurelifted import FormatChecker
from featurelifted import SchemaError
from featurelifted import ValidationError
from featurelifted import validate


def test_nested_errors_paths_combinators_and_messages() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["book", "movie"]},
                        "rating": {"anyOf": [{"type": "integer"}, {"type": "number"}]},
                    },
                    "required": ["kind", "rating"],
                },
            }
        },
        "required": ["items"],
    }

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors({"items": [{"kind": "album", "rating": "bad"}]}),
        key=lambda error: (list(error.path), error.validator),
    )

    assert [(list(error.path), error.validator) for error in errors] == [
        (["items", 0, "kind"], "enum"),
        (["items", 0, "rating"], "anyOf"),
    ]
    assert "album" in errors[0].message


def test_format_checker_schema_errors_and_additional_properties() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate(
            {"email": "not-an-email"},
            {
                "type": "object",
                "properties": {"email": {"type": "string", "format": "email"}},
            },
            format_checker=FormatChecker(),
        )

    assert list(excinfo.value.path) == ["email"]
    assert excinfo.value.validator == "format"

    validator = Draft202012Validator(
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
    )
    errors = list(validator.iter_errors({"name": "Ada", "extra": 1}))
    assert len(errors) == 1
    assert errors[0].validator == "additionalProperties"
    assert "extra" in errors[0].message

    with pytest.raises(SchemaError):
        Draft202012Validator.check_schema({"type": 123})


def test_oneof_and_const_keyword() -> None:
    schema = {
        "oneOf": [
            {"type": "string", "const": "yes"},
            {"type": "string", "const": "no"},
        ]
    }
    validator = Draft202012Validator(schema)
    assert validator.is_valid("yes")
    assert not validator.is_valid("maybe")
    errors = list(validator.iter_errors("maybe"))
    assert errors and errors[0].validator == "oneOf"
