# FeatureLift Task: SortedList core

Extract a task-scoped subset of `sortedcontainers` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    SortedList,
)
```

## Required API Details

- `SortedList(iterable=None, key=None)` class constructor
  - `SortedList._check(self)`
  - `SortedList._lists` attribute must exist on instances
  - `SortedList._maxes` attribute must exist on instances
  - `SortedList._reset(self, load)`
  - `SortedList.add(self, value)`
  - `SortedList.bisect(self, value)`
  - `SortedList.bisect_left(self, value)`
  - `SortedList.bisect_right(self, value)`
  - `SortedList.index(self, value, start=None, stop=None)`
  - `SortedList.irange(self, minimum=None, maximum=None, inclusive=(True, True), reverse=False)`
  - `SortedList.islice(self, start=None, stop=None, reverse=False)`
  - `SortedList.update(self, iterable)`
  - `SortedList.__delitem__(self, index)`

## Required Behavior

- The extracted feature must support this observable behavior: maintain sorted order with add/update and duplicate values. Required observable cases include add and iteration; no sortedcontainers import surface.
- The extracted feature must support this observable behavior: bisect_left/bisect_right and count/index on duplicate-heavy lists. Required observable cases include bisect and count; discard and remove; bisect with small load; index duplicate window.
- The extracted feature must support this observable behavior: positional indexing and slice reads with small load factors. Required observable cases include bisect with small load.
- The extracted feature must support this observable behavior: irange/islice inclusive bounds and reverse iteration. Required observable cases include add and iteration; irange inclusive bounds; islice reverse.
- The extracted feature must support this observable behavior: sublist merge/delete invariants validated via _check after _reset. Required observable cases include delete random invariants; check invariants.
- The package exposes the required task API paths `featurelifted.SortedList`, `featurelifted.SortedList._check`, `featurelifted.SortedList._lists`, `featurelifted.SortedList._maxes`, `featurelifted.SortedList._reset`, `featurelifted.SortedList.add`, `featurelifted.SortedList.bisect`, `featurelifted.SortedList.bisect_left`, `featurelifted.SortedList.bisect_right`, `featurelifted.SortedList.index`, `featurelifted.SortedList.irange`, `featurelifted.SortedList.islice`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sortedcontainers`.
- Do not implement SortedKeyList, SortedDict, SortedSet, and key-function variants.
- Do not implement benchmarks, upstream tests, docs, and packaging metadata.
- Do not implement original sortedcontainers import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: maintain sorted order with add/update and duplicate values. Required observable cases include add and iteration; no sortedcontainers import surface.
- **B002** — The extracted feature must support this observable behavior: bisect_left/bisect_right and count/index on duplicate-heavy lists. Required observable cases include bisect and count; discard and remove; bisect with small load; index duplicate window.
- **B003** — The extracted feature must support this observable behavior: positional indexing and slice reads with small load factors. Required observable cases include bisect with small load.
- **B004** — The extracted feature must support this observable behavior: irange/islice inclusive bounds and reverse iteration. Required observable cases include add and iteration; irange inclusive bounds; islice reverse.
- **B005** — The extracted feature must support this observable behavior: sublist merge/delete invariants validated via _check after _reset. Required observable cases include delete random invariants; check invariants.
- **B006** — The package exposes the required task API paths `featurelifted.SortedList`, `featurelifted.SortedList._check`, `featurelifted.SortedList._lists`, `featurelifted.SortedList._maxes`, `featurelifted.SortedList._reset`, `featurelifted.SortedList.add`, `featurelifted.SortedList.bisect`, `featurelifted.SortedList.bisect_left`, `featurelifted.SortedList.bisect_right`, `featurelifted.SortedList.index`, `featurelifted.SortedList.irange`, `featurelifted.SortedList.islice`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: sortedcontainers.
<!-- featureliftbench:behavior-clauses:end -->
