from __future__ import annotations

from featurelifted import Validator


def test_required_field_rejects_missing() -> None:
    validator = Validator({"name": {"type": "string", "required": True}})
    assert validator.validate({"name": "ada"})
    assert not validator.validate({})
    assert "name" in validator.errors


def test_type_rule_rejects_wrong_type() -> None:
    validator = Validator({"age": {"type": "integer"}})
    assert validator.validate({"age": 3})
    assert not validator.validate({"age": "three"})


def test_validate_returns_bool() -> None:
    validator = Validator({"active": {"type": "boolean"}})
    assert validator.validate({"active": True}) is True
    assert validator.validate({"active": "yes"}) is False
