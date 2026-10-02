# FeatureLift Task: Composable trafaret validation rules

Extract a task-scoped subset of `trafaret` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    And,
    DataError,
    Dict,
    Forward,
    Int,
    Key,
    Or,
    String,
)
```

## Required API Details

- `Int()` class constructor
- `String()` class constructor
- `Dict(schema: 'dict[str, Trafaret]', allow_extra: 'bool' = False)` class constructor
  - `Dict.check(self, value, path=())`
- `Key(name: 'str', validator: 'Trafaret', optional: 'bool' = False)` class constructor
- `Or(*options: 'Trafaret')` class constructor
  - `Or.check(self, value)`
- `And(*parts: 'Trafaret')` class constructor
  - `And.check(self, value)`
- `Forward()` class constructor
  - `Forward.set_type(self, target: 'Trafaret') -> 'None'`
  - `Forward.check(self, value)`
- `DataError` must be importable and raisable

## Required Behavior

- `Dict`, `Key`, `Or`, `And`, and `Forward` compose validation rules.
- DataError carries a path tuple for nested validation failures. Dict shorthand keys are required, so Dict({"name": String()}).check({}) raises DataError whose path is ("name",).
- `Forward.set_type` enables recursive schemas.
- The package exposes the required task API paths `featurelifted.Int`, `featurelifted.String`, `featurelifted.Dict`, `featurelifted.Dict.check`, `featurelifted.Key`, `featurelifted.Or`, `featurelifted.Or.check`, `featurelifted.And`, `featurelifted.And.check`, `featurelifted.Forward`, `featurelifted.Forward.set_type`, `featurelifted.Forward.check`, `featurelifted.DataError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `trafaret`.
- Forbidden path access: `repo/, trafaret/`.
- Do not implement network access.
- Do not implement mongo/internet validators.
- Do not implement async mixins.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `Dict`, `Key`, `Or`, `And`, and `Forward` compose validation rules.
- **B002** — DataError carries a path tuple for nested validation failures. Dict shorthand keys are required, so Dict({"name": String()}).check({}) raises DataError whose path is ("name",).
- **B003** — `Forward.set_type` enables recursive schemas.
- **B004** — The package exposes the required task API paths `featurelifted.Int`, `featurelifted.String`, `featurelifted.Dict`, `featurelifted.Dict.check`, `featurelifted.Key`, `featurelifted.Or`, `featurelifted.Or.check`, `featurelifted.And`, `featurelifted.And.check`, `featurelifted.Forward`, `featurelifted.Forward.set_type`, `featurelifted.Forward.check`, `featurelifted.DataError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: trafaret.
<!-- featureliftbench:behavior-clauses:end -->
