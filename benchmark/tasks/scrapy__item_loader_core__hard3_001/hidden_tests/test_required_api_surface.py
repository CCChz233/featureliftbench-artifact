"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Item,
    Field,
    ItemLoader,
    Compose,
    TakeFirst,
)


def test_required_api_surface():
    assert isinstance(Item, type)
    assert isinstance(Field, type)
    assert isinstance(ItemLoader, type)
    assert hasattr(ItemLoader, '__init__')
    assert hasattr(ItemLoader, 'add_value')
    assert hasattr(ItemLoader, 'load_item')
    assert ItemLoader is not None
    assert callable(Compose)
    assert callable(TakeFirst)
