# FeatureLift Task: Bidirectional mapping core

Extract a task-scoped subset of `bidict` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    bidict,
    frozenbidict,
    inverted,
    KeyAndValueDuplicationError,
    ON_DUP_RAISE,
    OrderedBidict,
    ValueDuplicationError,
)
```

## Required API Details

- `bidict(arg: 'MapOrItems[KT, VT]' = (), /, **kw: 'VT') -> 'None'`
- `frozenbidict(arg: 'MapOrItems[KT, VT]' = (), /, **kw: 'VT') -> 'None'`
- `OrderedBidict(arg: 'MapOrItems[KT, VT]' = (), /, **kw: 'VT') -> 'None'` class constructor
  - `OrderedBidict.keys(self) -> 'KeysView[KT]'`
  - `OrderedBidict.move_to_end(self, key: 'KT', last: 'bool' = True) -> 'None'`
- `ON_DUP_RAISE` constant must exist
- `ValueDuplicationError` must be importable and raisable
- `KeyAndValueDuplicationError` must be importable and raisable
- `inverted(arg: 'MapOrItems[KT, VT]') -> 'ItemsIter[VT, KT]'`

## Required Behavior

- The extracted feature must support this observable behavior: forward and inverse lookups on bidict and frozenbidict. Required observable cases include bidict forward and inverse lookup; frozenbidict is immutable; frozenbidict hash stable.
- The extracted feature must support this observable behavior: inverse view reflects live updates on mutable bidicts. Required observable cases include bidict inverse reflects updates; ordered move to end.
- The extracted feature must support this observable behavior: ON_DUP_RAISE duplicate value/key policies with typed errors. Required observable cases include on dup raise value collision; key and value duplication error.
- The extracted feature must support this observable behavior: OrderedBidict preserves insertion order and move_to_end. Required observable cases include ordered move to end.
- The extracted feature must support this observable behavior: inverted() iterator helper for value-key pairs. Required observable cases include inverted iterator.
- The package exposes the required task API paths `featurelifted.bidict`, `featurelifted.frozenbidict`, `featurelifted.OrderedBidict`, `featurelifted.OrderedBidict.keys`, `featurelifted.OrderedBidict.move_to_end`, `featurelifted.ON_DUP_RAISE`, `featurelifted.ValueDuplicationError`, `featurelifted.KeyAndValueDuplicationError`, `featurelifted.inverted` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `bidict`.
- Do not implement upstream benchmarks, docs, and test suite.
- Do not implement original bidict import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: forward and inverse lookups on bidict and frozenbidict. Required observable cases include bidict forward and inverse lookup; frozenbidict is immutable; frozenbidict hash stable.
- **B002** — The extracted feature must support this observable behavior: inverse view reflects live updates on mutable bidicts. Required observable cases include bidict inverse reflects updates; ordered move to end.
- **B003** — The extracted feature must support this observable behavior: ON_DUP_RAISE duplicate value/key policies with typed errors. Required observable cases include on dup raise value collision; key and value duplication error.
- **B004** — The extracted feature must support this observable behavior: OrderedBidict preserves insertion order and move_to_end. Required observable cases include ordered move to end.
- **B005** — The extracted feature must support this observable behavior: inverted() iterator helper for value-key pairs. Required observable cases include inverted iterator.
- **B006** — The package exposes the required task API paths `featurelifted.bidict`, `featurelifted.frozenbidict`, `featurelifted.OrderedBidict`, `featurelifted.OrderedBidict.keys`, `featurelifted.OrderedBidict.move_to_end`, `featurelifted.ON_DUP_RAISE`, `featurelifted.ValueDuplicationError`, `featurelifted.KeyAndValueDuplicationError`, `featurelifted.inverted` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: bidict.
<!-- featureliftbench:behavior-clauses:end -->
