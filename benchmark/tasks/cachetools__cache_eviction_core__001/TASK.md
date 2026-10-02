# FeatureLift Task: Cache eviction core

Extract a task-scoped subset of `cachetools` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    cached,
    hashkey,
    LFUCache,
    LRUCache,
    TTLCache,
    typedkey,
)
```

## Required API Details

- `LRUCache(maxsize, getsizeof=None)` class constructor
  - `LRUCache.maxsize` attribute must exist on instances
  - `LRUCache.__contains__(self, key)`
  - `LRUCache.__getitem__(self, key, cache_getitem=<function Cache.__getitem__ at 0x102f4f4c0>)`
  - `LRUCache.__setitem__(self, key, value, cache_setitem=<function Cache.__setitem__ at 0x102f4f560>)`
- `TTLCache(maxsize, ttl, timer=<built-in function monotonic>, getsizeof=None)` class constructor
  - `TTLCache.__contains__(self, key)`
  - `TTLCache.__getitem__(self, key, cache_getitem=<function Cache.__getitem__ at 0x102f4f4c0>)`
  - `TTLCache.__setitem__(self, key, value, cache_setitem=<function Cache.__setitem__ at 0x102f4f560>)`
- `LFUCache(maxsize, getsizeof=None)` class constructor
  - `LFUCache.__contains__(self, key)`
  - `LFUCache.__getitem__(self, key, cache_getitem=<function Cache.__getitem__ at 0x102f4f4c0>)`
  - `LFUCache.__setitem__(self, key, value, cache_setitem=<function Cache.__setitem__ at 0x102f4f560>)`
- `cached(cache, key=<function hashkey>, lock=None, condition=None, info=False)`
- `hashkey(*args, **kwargs)`
- `typedkey(*args, **kwargs)`

## Required Behavior

- The extracted feature must support this observable behavior: LRU eviction order with touch-on-get and maxsize enforcement. Required observable cases include lru cache basic get set; lru eviction order; lru maxsize enforced.
- The extracted feature must support this observable behavior: LFU frequency buckets and least-frequent eviction. Required observable cases include lfu evicts lowest frequency.
- The extracted feature must support this observable behavior: TTL expiry with injectable timer and doubly-linked expiry list. Required observable cases include ttl expiry with mock timer.
- The extracted feature must support this observable behavior: cached decorator memoization with optional cache_info hits/misses. Required observable cases include ttl cache stores value; cached decorator memoizes; cached info tracks hits and misses.
- The extracted feature must support this observable behavior: hashkey and typedkey cache key functions for decorator kwargs and types. Required observable cases include ttl cache stores value; typedkey distinguishes value types.
- The package exposes the required task API paths `featurelifted.LRUCache`, `featurelifted.LRUCache.maxsize`, `featurelifted.LRUCache.__contains__`, `featurelifted.LRUCache.__getitem__`, `featurelifted.LRUCache.__setitem__`, `featurelifted.TTLCache`, `featurelifted.TTLCache.__contains__`, `featurelifted.TTLCache.__getitem__`, `featurelifted.TTLCache.__setitem__`, `featurelifted.LFUCache`, `featurelifted.LFUCache.__contains__`, `featurelifted.LFUCache.__getitem__`, and 4 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `cachetools`.
- Do not implement async caches, cachedmethod, func.lru_cache wrappers, and TLRUCache.
- Do not implement upstream benchmarks, docs, tests, and packaging metadata.
- Do not implement original cachetools import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: LRU eviction order with touch-on-get and maxsize enforcement. Required observable cases include lru cache basic get set; lru eviction order; lru maxsize enforced.
- **B002** — The extracted feature must support this observable behavior: LFU frequency buckets and least-frequent eviction. Required observable cases include lfu evicts lowest frequency.
- **B003** — The extracted feature must support this observable behavior: TTL expiry with injectable timer and doubly-linked expiry list. Required observable cases include ttl expiry with mock timer.
- **B004** — The extracted feature must support this observable behavior: cached decorator memoization with optional cache_info hits/misses. Required observable cases include ttl cache stores value; cached decorator memoizes; cached info tracks hits and misses.
- **B005** — The extracted feature must support this observable behavior: hashkey and typedkey cache key functions for decorator kwargs and types. Required observable cases include ttl cache stores value; typedkey distinguishes value types.
- **B006** — The package exposes the required task API paths `featurelifted.LRUCache`, `featurelifted.LRUCache.maxsize`, `featurelifted.LRUCache.__contains__`, `featurelifted.LRUCache.__getitem__`, `featurelifted.LRUCache.__setitem__`, `featurelifted.TTLCache`, `featurelifted.TTLCache.__contains__`, `featurelifted.TTLCache.__getitem__`, `featurelifted.TTLCache.__setitem__`, `featurelifted.LFUCache`, `featurelifted.LFUCache.__contains__`, `featurelifted.LFUCache.__getitem__`, and 4 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: cachetools.
<!-- featureliftbench:behavior-clauses:end -->
