# FeatureLift Task: HookCaller historic wrapper ordering

Extract a task-scoped subset of `pluggy` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    HookCaller,
)
```

## Required API Details

- `HookCaller(name: 'str', *, firstresult: 'bool' = False, historic: 'bool' = False) -> 'None'` class constructor
  - `HookCaller.add_hookimpl(self, function: 'Callable[..., Any]', *, tryfirst: 'bool' = False, trylast: 'bool' = False, optionalhook: 'bool' = False) -> 'None'`
  - `HookCaller.call_extra(self, methods: 'list[Callable[..., Any]]', kwargs: 'dict[str, Any]') -> 'Any'`
  - `HookCaller.get_hookimpls(self) -> 'list[HookImpl]'`

## Required Behavior

- `call_extra()` temporarily adds hook implementations without mutating permanent state.
- `tryfirst`/`trylast` options control hookimpl ordering.
- When HookCaller invokes multiple implementations, it aggregates results in hook order, honors firstresult, and lets wrappers observe or modify the outcome.
- The package exposes the required task API paths `featurelifted.HookCaller`, `featurelifted.HookCaller.add_hookimpl`, `featurelifted.HookCaller.call_extra`, `featurelifted.HookCaller.get_hookimpls` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pluggy`.
- Forbidden path access: `repo/, pluggy/`.
- Do not implement network access.
- Do not implement plugin manager discovery.
- Do not implement entry point loading.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `call_extra()` temporarily adds hook implementations without mutating permanent state.
- **B002** — `tryfirst`/`trylast` options control hookimpl ordering.
- **B003** — When HookCaller invokes multiple implementations, it aggregates results in hook order, honors firstresult, and lets wrappers observe or modify the outcome.
- **B004** — The package exposes the required task API paths `featurelifted.HookCaller`, `featurelifted.HookCaller.add_hookimpl`, `featurelifted.HookCaller.call_extra`, `featurelifted.HookCaller.get_hookimpls` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: pluggy.
<!-- featureliftbench:behavior-clauses:end -->
