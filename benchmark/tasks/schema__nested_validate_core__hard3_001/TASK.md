# FeatureLift Task: Schema Optional Or And

Extract a task-scoped subset of `schema` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    And,
    Optional,
    Or,
    Schema,
    SchemaError,
)
```

## Required API Details

- `Schema(schema: 'Any') -> 'None'` class constructor
  - `Schema.validate(self, data: 'Any') -> 'Any'`
- `Optional(key: 'str', default: 'Any' = Ellipsis) -> 'None'` class constructor
- `Or(*validators: 'Any') -> 'None'` class constructor
  - `Or.validate(self, data: 'Any') -> 'Any'`
- `And(*validators: 'Any') -> 'None'` class constructor
  - `And.validate(self, data: 'Any') -> 'Any'`
- `SchemaError` must be importable and raisable

## Required Behavior

- `Schema` validates nested dicts with type and literal rules.
- `Optional` supplies defaults for missing keys.
- Or accepts the first validating alternative, while And applies each validator in sequence. A callable And step transforms the value, so And(str, lambda s: s.upper()).validate("hi") returns "HI", and SchemaError is reported when composition fails.
- The package exposes the required task API paths `featurelifted.Schema`, `featurelifted.Schema.validate`, `featurelifted.Optional`, `featurelifted.Or`, `featurelifted.Or.validate`, `featurelifted.And`, `featurelifted.And.validate`, `featurelifted.SchemaError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `schema`.
- Forbidden path access: `repo/, schema/`.
- Do not implement network access.
- Do not implement full package surface.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `Schema` validates nested dicts with type and literal rules.
- **B002** — `Optional` supplies defaults for missing keys.
- **B003** — Or accepts the first validating alternative, while And applies each validator in sequence. A callable And step transforms the value, so And(str, lambda s: s.upper()).validate("hi") returns "HI", and SchemaError is reported when composition fails.
- **B004** — The package exposes the required task API paths `featurelifted.Schema`, `featurelifted.Schema.validate`, `featurelifted.Optional`, `featurelifted.Or`, `featurelifted.Or.validate`, `featurelifted.And`, `featurelifted.And.validate`, `featurelifted.SchemaError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: schema.
<!-- featureliftbench:behavior-clauses:end -->
