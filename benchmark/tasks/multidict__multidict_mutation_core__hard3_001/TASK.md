# FeatureLift Task: Case-insensitive multidict mutation and proxy behavior

Extract a task-scoped subset of `multidict` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CIMultiDict,
    CIMultiDictProxy,
    MultiDict,
    MultiDictProxy,
)
```

## Required API Details

- `MultiDict(*args, **kwargs) -> 'None'` class constructor
  - `MultiDict.add(self, key: 'str', value: 'object') -> 'None'`
  - `MultiDict.popall(self, key: 'str') -> 'list[object]'`
  - `MultiDict.popone(self, key: 'str', default=Ellipsis)`
  - `MultiDict.__getitem__(self, key: 'str') -> 'object'`
- `CIMultiDict(*args, **kwargs) -> 'None'` class constructor
  - `CIMultiDict.add(self, key: 'str', value: 'object') -> 'None'`
  - `CIMultiDict.getall(self, key: 'str') -> 'list[object]'`
  - `CIMultiDict.__getitem__(self, key: 'str') -> 'object'`
- `MultiDictProxy(base: 'MultiDict') -> 'None'` class constructor
- `CIMultiDictProxy(base: 'CIMultiDict') -> 'None'` class constructor
  - `CIMultiDictProxy.add(self, key: 'str', value: 'object') -> 'None'`

## Required Behavior

- MultiDict preserves repeated values and insertion order while CIMultiDict applies the same mutations using case-insensitive string keys.
- getall and getone retrieve repeated values, while popone removes the most recent matching value and popall removes every matching value.
- MultiDictProxy and CIMultiDictProxy reflect subsequent mutations of their underlying mappings without exposing independent copied state.
- CIMultiDict folds keys case-insensitively for lookup, replacement, deletion, and repeated-value operations.
- The package exposes the required task API paths `featurelifted.MultiDict`, `featurelifted.MultiDict.add`, `featurelifted.MultiDict.popall`, `featurelifted.MultiDict.popone`, `featurelifted.MultiDict.__getitem__`, `featurelifted.CIMultiDict`, `featurelifted.CIMultiDict.add`, `featurelifted.CIMultiDict.getall`, `featurelifted.CIMultiDict.__getitem__`, `featurelifted.MultiDictProxy`, `featurelifted.CIMultiDictProxy`, `featurelifted.CIMultiDictProxy.add` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `multidict`.
- Forbidden path access: `repo/, multidict/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement C extension implementation.
- Do not implement typing-only modules.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — MultiDict preserves repeated values and insertion order while CIMultiDict applies the same mutations using case-insensitive string keys.
- **B002** — getall and getone retrieve repeated values, while popone removes the most recent matching value and popall removes every matching value.
- **B003** — MultiDictProxy and CIMultiDictProxy reflect subsequent mutations of their underlying mappings without exposing independent copied state.
- **B004** — CIMultiDict folds keys case-insensitively for lookup, replacement, deletion, and repeated-value operations.
- **B005** — The package exposes the required task API paths `featurelifted.MultiDict`, `featurelifted.MultiDict.add`, `featurelifted.MultiDict.popall`, `featurelifted.MultiDict.popone`, `featurelifted.MultiDict.__getitem__`, `featurelifted.CIMultiDict`, `featurelifted.CIMultiDict.add`, `featurelifted.CIMultiDict.getall`, `featurelifted.CIMultiDict.__getitem__`, `featurelifted.MultiDictProxy`, `featurelifted.CIMultiDictProxy`, `featurelifted.CIMultiDictProxy.add` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: multidict.
<!-- featureliftbench:behavior-clauses:end -->
