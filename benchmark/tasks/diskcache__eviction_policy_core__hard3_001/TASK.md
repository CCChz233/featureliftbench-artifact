# FeatureLift Task: EvictionPolicyPlanner

Extract a task-scoped subset of `diskcache` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    EvictionPolicyPlanner,
)
```

## Required API Details

- `EvictionPolicyPlanner() -> 'None'` class constructor
  - `EvictionPolicyPlanner.evict(self, max_size: 'int', *, tag: 'str | None' = None) -> 'list[str]'`
  - `EvictionPolicyPlanner.purge_expired(self, now: 'float') -> 'list[str]'`
  - `EvictionPolicyPlanner.set(self, key: 'str', *, size: 'int' = 1, expire_at: 'float | None' = None, tag: 'str | None' = None) -> 'None'`
  - `EvictionPolicyPlanner.total_size(self) -> 'int'`
  - `EvictionPolicyPlanner.touch(self, key: 'str') -> 'None'`

## Required Behavior

- `touch(key)` updates access order for LRU decisions.
- `evict(max_size, tag=...)` removes least-recently-used entries until under budget.
- When purge_expired runs, expired entries are removed before size-based eviction and unexpired entries remain available.
- The package exposes the required task API paths `featurelifted.EvictionPolicyPlanner`, `featurelifted.EvictionPolicyPlanner.evict`, `featurelifted.EvictionPolicyPlanner.purge_expired`, `featurelifted.EvictionPolicyPlanner.set`, `featurelifted.EvictionPolicyPlanner.total_size`, `featurelifted.EvictionPolicyPlanner.touch` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `diskcache`.
- Forbidden path access: `repo/, diskcache/`.
- Do not implement network access.
- Do not implement sqlite disk backend.
- Do not implement file I/O.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `touch(key)` updates access order for LRU decisions.
- **B002** — `evict(max_size, tag=...)` removes least-recently-used entries until under budget.
- **B003** — When purge_expired runs, expired entries are removed before size-based eviction and unexpired entries remain available.
- **B004** — The package exposes the required task API paths `featurelifted.EvictionPolicyPlanner`, `featurelifted.EvictionPolicyPlanner.evict`, `featurelifted.EvictionPolicyPlanner.purge_expired`, `featurelifted.EvictionPolicyPlanner.set`, `featurelifted.EvictionPolicyPlanner.total_size`, `featurelifted.EvictionPolicyPlanner.touch` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: diskcache.
<!-- featureliftbench:behavior-clauses:end -->
