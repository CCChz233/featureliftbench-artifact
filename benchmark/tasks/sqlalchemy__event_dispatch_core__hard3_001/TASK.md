# FeatureLift Task: Event registry dispatch core

Extract a task-scoped subset of `sqlalchemy` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    dispatch,
    EventTarget,
    listen,
    remove,
)
```

## Required API Details

- `listen(target: 'type', identifier: 'str', fn: 'Callable', once: 'bool' = False, propagate: 'bool' = False, named: 'bool' = False) -> 'None'`
- `remove(target: 'type', identifier: 'str', fn: 'Callable') -> 'None'`
- `dispatch(target: 'type', identifier: 'str', *args, **kwargs) -> 'None'`
- `EventTarget()` class constructor

## Required Behavior

- `listen` registers listeners for `(target, identifier)` pairs.
- `dispatch` invokes active listeners; `once=True` listeners run at most once.
- `remove` during dispatch must not break in-flight dispatch.
- `propagate=True` also registers on subclasses.
- `named=True` invokes listeners with keyword arguments.
- The package exposes the required task API paths `featurelifted.listen`, `featurelifted.remove`, `featurelifted.dispatch`, `featurelifted.EventTarget` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sqlalchemy`.
- Forbidden path access: `repo/, sqlalchemy/`.
- Do not implement network access.
- Do not implement ORM/engine/database access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `listen` registers listeners for `(target, identifier)` pairs.
- **B002** — `dispatch` invokes active listeners; `once=True` listeners run at most once.
- **B003** — `remove` during dispatch must not break in-flight dispatch.
- **B004** — `propagate=True` also registers on subclasses.
- **B005** — `named=True` invokes listeners with keyword arguments.
- **B006** — The package exposes the required task API paths `featurelifted.listen`, `featurelifted.remove`, `featurelifted.dispatch`, `featurelifted.EventTarget` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: sqlalchemy.
<!-- featureliftbench:behavior-clauses:end -->
