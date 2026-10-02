
import pytest

from featurelifted import Compose, Field, Item, ItemLoader, TakeFirst


class Product(Item):
    name = Field(output_processor=TakeFirst())
    tags = Field(input_processor=lambda x: x.upper(), output_processor=Compose(list))


def test_compose_output_processor_and_parent_defaults():
    loader = ItemLoader(item=Product)
    loader.add_value("tags", "a")
    loader.add_value("tags", "b")
    item = loader.load_item()
    assert item["tags"] == ["A", "B"]
    child = ItemLoader(parent=loader, item=Product)
    assert type(child.default_output_processor) is type(loader.default_output_processor)


def test_missing_field_raises():
    loader = ItemLoader(item=Product)
    with pytest.raises(KeyError):
        loader.add_value("missing", 1)
