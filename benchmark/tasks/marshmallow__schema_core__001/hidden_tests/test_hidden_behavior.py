from __future__ import annotations

import pytest

from featurelifted import EXCLUDE, RAISE, Schema, ValidationError, fields
from featurelifted.decorators import post_load, validates_schema


class ItemSchema(Schema):
    qty = fields.Int(required=True)
    sku = fields.Str(required=True)


class OrderSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    items = fields.List(fields.Nested(ItemSchema), required=True)
    note = fields.Str(load_default="")

    @validates_schema
    def validate_items(self, data, **kwargs):
        if not data.get("items"):
            raise ValidationError("items required", "items")

    @post_load
    def add_total(self, data, **kwargs):
        data["total_qty"] = sum(item["qty"] for item in data["items"])
        return data


def test_unknown_exclude_post_load_and_nested_errors() -> None:
    schema = OrderSchema()
    loaded = schema.load(
        {
            "items": [{"sku": "A", "qty": 2}, {"sku": "B", "qty": 1}],
            "extra": True,
        }
    )
    assert loaded["total_qty"] == 3
    assert "extra" not in loaded

    with pytest.raises(ValidationError) as excinfo:
        schema.load({"items": [{"sku": "A", "qty": "nope"}]})
    assert "qty" in str(excinfo.value.messages)


def test_many_dump_partial_and_raise_unknown() -> None:
    class TagSchema(Schema):
        class Meta:
            unknown = RAISE

        name = fields.Str(required=True)

    schema = TagSchema()
    with pytest.raises(ValidationError):
        schema.load({"name": "x", "surprise": 1})

    many = TagSchema(many=True)
    dumped = many.dump([{"name": "a"}, {"name": "b"}])
    assert dumped == [{"name": "a"}, {"name": "b"}]
