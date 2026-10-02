from __future__ import annotations

from featurelifted import LRUCache, TTLCache, cached


def test_lru_cache_basic_get_set() -> None:
    cache = LRUCache(maxsize=4)
    cache["a"] = 1
    cache["b"] = 2
    assert cache["a"] == 1
    assert cache["b"] == 2
    assert len(cache) == 2


def test_ttl_cache_stores_value() -> None:
    cache = TTLCache(maxsize=4, ttl=60)
    cache[1] = "one"
    assert cache[1] == "one"
    assert 1 in cache


def test_cached_decorator_memoizes() -> None:
    cache = LRUCache(maxsize=8)
    calls: list[tuple[int, int]] = []

    @cached(cache=cache)
    def add(a: int, b: int) -> int:
        calls.append((a, b))
        return a + b

    assert add(2, 3) == 5
    assert add(2, 3) == 5
    assert calls == [(2, 3)]
