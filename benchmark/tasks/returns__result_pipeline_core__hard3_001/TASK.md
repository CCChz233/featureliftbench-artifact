# FeatureLift Task: Result Success Failure safe

Extract a task-scoped subset of `returns` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Failure,
    Result,
    safe,
    Success,
)
```

## Required API Details

- `Result()` class constructor
- `Success(value: 'T') -> 'None'` class constructor
  - `Success.map(self, function: 'Callable[[T], U]') -> 'Result[U, E]'`
  - `Success.value` attribute must exist on instances
  - `Success.bind(self, function: 'Callable[[T], Result[U, E]]') -> 'Result[U, E]'`
- `Failure(error: 'E') -> 'None'` class constructor
  - `Failure.failure` attribute must exist on instances
  - `Failure.map(self, function: 'Callable[[T], U]') -> 'Result[U, E]'`
  - `Failure.bind(self, function: 'Callable[[T], Result[U, E]]') -> 'Result[U, E]'`
- `safe(function: 'Callable[..., T] | None' = None, *, exceptions: 'tuple[type[BaseException], ...]' = (<class 'Exception'>,))`

## Required Behavior

- When map or bind is called, Success transforms its value while Failure short-circuits and preserves its error.
- Success and Failure expose their contained value or error through the declared Result container operations.
- `@safe` wraps callables and maps exceptions to `Failure`.
- The package exposes the required task API paths `featurelifted.Result`, `featurelifted.Success`, `featurelifted.Success.map`, `featurelifted.Success.value`, `featurelifted.Success.bind`, `featurelifted.Failure`, `featurelifted.Failure.failure`, `featurelifted.Failure.map`, `featurelifted.Failure.bind`, `featurelifted.safe` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `returns`.
- Forbidden path access: `repo/, returns/`.
- Do not implement network access.
- Do not implement Maybe/IO containers.
- Do not implement async helpers.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When map or bind is called, Success transforms its value while Failure short-circuits and preserves its error.
- **B002** — Success and Failure expose their contained value or error through the declared Result container operations.
- **B003** — `@safe` wraps callables and maps exceptions to `Failure`.
- **B004** — The package exposes the required task API paths `featurelifted.Result`, `featurelifted.Success`, `featurelifted.Success.map`, `featurelifted.Success.value`, `featurelifted.Success.bind`, `featurelifted.Failure`, `featurelifted.Failure.failure`, `featurelifted.Failure.map`, `featurelifted.Failure.bind`, `featurelifted.safe` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: returns.
<!-- featureliftbench:behavior-clauses:end -->
