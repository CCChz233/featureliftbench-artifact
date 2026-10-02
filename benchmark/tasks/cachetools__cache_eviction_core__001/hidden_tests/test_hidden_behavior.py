from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import LFUCache, LRUCache, TTLCache, cached, typedkey


class _FakeTimer:
    def __init__(self) -> None:
        self._now = 0.0

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def test_lru_eviction_order() -> None:
    cache = LRUCache(maxsize=2)
    cache[1] = "a"
    cache[2] = "b"
    cache[3] = "c"
    assert 1 not in cache
    assert cache[2] == "b"
    assert cache[3] == "c"

    cache[2]
    cache[4] = "d"
    assert 3 not in cache
    assert cache[2] == "b"
    assert cache[4] == "d"


def test_lfu_evicts_lowest_frequency() -> None:
    cache = LFUCache(maxsize=2)
    cache[1] = "a"
    cache[1]
    cache[2] = "b"
    cache[3] = "c"
    assert 1 in cache
    assert 2 not in cache
    assert 3 in cache


def test_ttl_expiry_with_mock_timer() -> None:
    timer = _FakeTimer()
    cache = TTLCache(maxsize=4, ttl=5, timer=timer)
    cache["token"] = "secret"
    assert cache["token"] == "secret"

    timer.advance(6)
    assert "token" not in cache
    with pytest.raises(KeyError):
        _ = cache["token"]


def test_lru_maxsize_enforced() -> None:
    cache = LRUCache(maxsize=3)
    assert cache.maxsize == 3
    for index in range(6):
        cache[index] = index
    assert len(cache) == 3
    assert 0 not in cache
    assert 1 not in cache
    assert 2 not in cache
    assert 3 in cache and 4 in cache and 5 in cache


def test_typedkey_distinguishes_value_types() -> None:
    cache = LRUCache(maxsize=8)
    calls: list[object] = []

    @cached(cache=cache, key=typedkey)
    def identity(value: object) -> object:
        calls.append(value)
        return value

    identity(1)
    identity(1.0)
    assert len(calls) == 2


def test_cached_info_tracks_hits_and_misses() -> None:
    cache = LRUCache(maxsize=8)

    @cached(cache=cache, info=True)
    def double(value: int) -> int:
        return value * 2

    assert double(3) == 6
    assert double(3) == 6
    info = double.cache_info()
    assert info.hits == 1
    assert info.misses == 1


def test_no_cachetools_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from cachetools|import cachetools)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
