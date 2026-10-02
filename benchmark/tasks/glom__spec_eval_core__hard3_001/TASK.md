# FeatureLift Task: Spec evaluation with Coalesce, T, and error paths

Extract a task-scoped subset of `glom` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Coalesce,
    glom,
    PathAccessError,
    T,
)
```

## Required API Details

- `glom(target, spec, default=None)`
- `T` object must exist
- `Coalesce(specs: 'list[Any]', default: 'Any' = None) -> None` class constructor
- `PathAccessError` must be importable and raisable

## Required Behavior

- `glom` evaluates dict/list/tuple specs, dotted path strings, callables, `T`, and `Coalesce`.
- `Coalesce` returns the first successful child spec or a configured default.
- When a T expression is evaluated, attribute and item traversal start from the current target and compose in expression order.
- When dotted-path or T traversal cannot access a requested component, glom raises PathAccessError unless a declared default handles the failure.
- The package exposes the required task API paths `featurelifted.glom`, `featurelifted.T`, `featurelifted.Coalesce`, `featurelifted.PathAccessError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `glom`.
- Forbidden path access: `repo/, glom/`.
- Do not implement network access.
- Do not implement CLI.
- Do not implement streaming/grouping operators beyond target subset.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `glom` evaluates dict/list/tuple specs, dotted path strings, callables, `T`, and `Coalesce`.
- **B002** — `Coalesce` returns the first successful child spec or a configured default.
- **B003** — When a T expression is evaluated, attribute and item traversal start from the current target and compose in expression order.
- **B004** — When dotted-path or T traversal cannot access a requested component, glom raises PathAccessError unless a declared default handles the failure.
- **B005** — The package exposes the required task API paths `featurelifted.glom`, `featurelifted.T`, `featurelifted.Coalesce`, `featurelifted.PathAccessError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: glom.
<!-- featureliftbench:behavior-clauses:end -->
