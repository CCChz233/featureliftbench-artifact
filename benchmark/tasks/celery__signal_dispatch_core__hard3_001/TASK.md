# FeatureLift Task: Signal registry and receiver dispatch

Extract a task-scoped subset of `celery` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Signal,
)
```

## Required API Details

- `Signal(name: 'str' = 'signal') -> 'None'` class constructor
  - `Signal.connect(self, receiver: 'Callable[..., Any]', sender: 'Any' = None, dispatch_uid: 'Any' = None, weak: 'bool' = True) -> 'Callable[..., Any]'`
  - `Signal.send(self, sender: 'Any' = None, **kwargs) -> 'list[tuple[Any, Any]]'`

## Required Behavior

- When connect registers a receiver, dispatch invokes it once unless dispatch_uid intentionally deduplicates the registration.
- When a receiver is registered for a sender, dispatch invokes it only for matching sender values while sender-agnostic receivers still run.
- When a signal is dispatched, the returned list preserves receiver order and pairs each receiver with its response or captured exception.
- When a weakly referenced receiver is garbage-collected, later dispatches omit and clean up that dead receiver.
- The package exposes the required task API paths `featurelifted.Signal`, `featurelifted.Signal.connect`, `featurelifted.Signal.send` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `celery`.
- Forbidden path access: `repo/, celery/`.
- Do not implement network access.
- Do not implement broker/task execution.
- Do not implement worker runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When connect registers a receiver, dispatch invokes it once unless dispatch_uid intentionally deduplicates the registration.
- **B002** — When a receiver is registered for a sender, dispatch invokes it only for matching sender values while sender-agnostic receivers still run.
- **B003** — When a signal is dispatched, the returned list preserves receiver order and pairs each receiver with its response or captured exception.
- **B004** — When a weakly referenced receiver is garbage-collected, later dispatches omit and clean up that dead receiver.
- **B005** — The package exposes the required task API paths `featurelifted.Signal`, `featurelifted.Signal.connect`, `featurelifted.Signal.send` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: celery.
<!-- featureliftbench:behavior-clauses:end -->
