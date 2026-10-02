"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    LRUCache,
    TTLCache,
    LFUCache,
    cached,
    hashkey,
    typedkey,
)


def test_required_api_surface():
    assert isinstance(LRUCache, type)
    assert LRUCache is not None
    assert hasattr(LRUCache, '__contains__')
    assert hasattr(LRUCache, '__getitem__')
    assert hasattr(LRUCache, '__setitem__')
    assert isinstance(TTLCache, type)
    assert hasattr(TTLCache, '__contains__')
    assert hasattr(TTLCache, '__getitem__')
    assert hasattr(TTLCache, '__setitem__')
    assert isinstance(LFUCache, type)
    assert hasattr(LFUCache, '__contains__')
    assert hasattr(LFUCache, '__getitem__')
    assert hasattr(LFUCache, '__setitem__')
    assert callable(cached)
    assert callable(hashkey)
    assert callable(typedkey)
