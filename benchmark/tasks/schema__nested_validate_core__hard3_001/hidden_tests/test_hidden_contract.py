
import pytest

from featurelifted import And, Optional, Or, Schema, SchemaError


def test_optional_default():
    validator = Schema({Optional("tag", default="latest"): str})
    assert validator.validate({})["tag"] == "latest"


def test_or_and_composition():
    validator = Or(int, str)
    assert validator.validate("x") == "x"
    assert And(str, lambda s: s.upper()).validate("hi") == "HI"


def test_extra_keys_rejected():
    validator = Schema({"name": str})
    with pytest.raises(SchemaError):
        validator.validate({"name": "Ada", "extra": 1})
