# FeatureLift Task: Configurator action conflict resolver

Extract a task-scoped subset of `pyramid` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ActionRegistry,
    ConfigurationConflictError,
)
```

## Required API Details

- `ActionRegistry() -> 'None'` class constructor
  - `ActionRegistry.commit(self) -> 'list[Any]'`
  - `ActionRegistry.introspect(self, category: 'str | None' = None) -> 'list[Action]'`
  - `ActionRegistry.register(self, discriminator: 'Any', callable: 'Callable[..., Any] | None' = None, order: 'int' = 0, args=(), kw=None, category: 'str | None' = None) -> 'None'`
- `ConfigurationConflictError` must be importable and raisable

## Required Behavior

- `register` queues actions with discriminators and order values.
- `commit` executes actions in order; duplicate discriminators raise `ConfigurationConflictError`.
- None discriminators never conflict, and commit() returns the list of callable results in registration order rather than the queued action records.
- `introspect(category=...)` filters committed actions.
- The package exposes the required task API paths `featurelifted.ActionRegistry`, `featurelifted.ActionRegistry.commit`, `featurelifted.ActionRegistry.introspect`, `featurelifted.ActionRegistry.register`, `featurelifted.ConfigurationConflictError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pyramid`.
- Forbidden path access: `repo/, pyramid/`.
- Do not implement network access.
- Do not implement WSGI server.
- Do not implement full web framework startup.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `register` queues actions with discriminators and order values.
- **B002** — `commit` executes actions in order; duplicate discriminators raise `ConfigurationConflictError`.
- **B003** — None discriminators never conflict, and commit() returns the list of callable results in registration order rather than the queued action records.
- **B004** — `introspect(category=...)` filters committed actions.
- **B005** — The package exposes the required task API paths `featurelifted.ActionRegistry`, `featurelifted.ActionRegistry.commit`, `featurelifted.ActionRegistry.introspect`, `featurelifted.ActionRegistry.register`, `featurelifted.ConfigurationConflictError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: pyramid.
<!-- featureliftbench:behavior-clauses:end -->
