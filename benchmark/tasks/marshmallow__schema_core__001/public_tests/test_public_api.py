from __future__ import annotations

import pytest

from featurelifted import EXCLUDE, Schema, ValidationError, fields


class ProfileSchema(Schema):
    city = fields.Str(required=True)


class UserSchema(Schema):
    name = fields.Str(required=True)
    age = fields.Int(validate=lambda n: n >= 0)
    profile = fields.Nested(ProfileSchema)


def test_load_dump_nested_schema() -> None:
    schema = UserSchema()
    loaded = schema.load({"name": "Ada", "age": 3, "profile": {"city": "Paris"}})
    assert loaded["profile"]["city"] == "Paris"
    dumped = schema.dump(loaded)
    assert dumped["name"] == "Ada"

    with pytest.raises(ValidationError):
        schema.load({"age": 3, "profile": {"city": "Paris"}})
