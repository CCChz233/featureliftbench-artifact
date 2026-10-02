# FeatureLift Task: pytest skipif condition evaluator

Extract a task-scoped subset of `pytest` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    EvalContext,
    evaluate_condition,
    Mark,
)
```

## Required API Details

- `Mark(name: 'str', kwargs: 'Mapping[str, Any]' = <factory>) -> None` class constructor
- `EvalContext(config: 'Any' = None, obj_globals: 'Mapping[str, Any] | None' = None, markeval_namespace: 'Sequence[Mapping[str, Any]]' = ()) -> None` class constructor
- `evaluate_condition(context: 'EvalContext', mark: 'Mark', condition: 'object') -> 'tuple[bool, str]'`

## Required Behavior

- The extracted feature must support this observable behavior: evaluate string conditions via compile/eval with allowed globals. Required observable cases include string condition true; obj globals merged; invalid syntax raises.
- The extracted feature must support this observable behavior: evaluate boolean conditions directly. Required observable cases include boolean condition; obj globals merged.
- The extracted feature must support this observable behavior: merge markeval_namespace mappings into eval globals. Required observable cases include markeval namespace merged; obj globals merged.
- The extracted feature must support this observable behavior: return (result, reason) tuple with default reason for string conditions. Required observable cases include string condition true; obj globals merged.
- The package exposes the required task API paths `featurelifted.Mark`, `featurelifted.EvalContext`, `featurelifted.evaluate_condition` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pytest, _pytest`.
- Do not implement full skip/xfail mark application during test run.
- Do not implement pytest item/collector integration.
- Do not implement xfail strict/run/raises handling.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: evaluate string conditions via compile/eval with allowed globals. Required observable cases include string condition true; obj globals merged; invalid syntax raises.
- **B002** — The extracted feature must support this observable behavior: evaluate boolean conditions directly. Required observable cases include boolean condition; obj globals merged.
- **B003** — The extracted feature must support this observable behavior: merge markeval_namespace mappings into eval globals. Required observable cases include markeval namespace merged; obj globals merged.
- **B004** — The extracted feature must support this observable behavior: return (result, reason) tuple with default reason for string conditions. Required observable cases include string condition true; obj globals merged.
- **B005** — The package exposes the required task API paths `featurelifted.Mark`, `featurelifted.EvalContext`, `featurelifted.evaluate_condition` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: pytest, _pytest.
<!-- featureliftbench:behavior-clauses:end -->
