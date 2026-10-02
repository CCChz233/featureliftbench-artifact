
from featurelifted import Field, Item, ItemLoader, TakeFirst


class Product(Item):
    name = Field()
    price = Field(input_processor=lambda x: x.strip(), output_processor=TakeFirst())


def test_item_loader_applies_processors():
    loader = ItemLoader(item=Product)
    loader.add_value("name", "  hat ")
    loader.add_value("price", "9")
    item = loader.load_item()
    assert item["name"] == "  hat "
    assert item["price"] == "9"
