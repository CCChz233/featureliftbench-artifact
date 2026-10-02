# FeatureLift Task: field_validator before/after

Extract a task-scoped subset of `pydantic` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    BaseModel,
    field_validator,
    ValidationError,
)
```

## Required API Details

- `field_validator(*fields: 'str', mode: 'str' = 'after')`
- `BaseModel(**data: 'Any') -> 'None'` class constructor
- `ValidationError` must be importable and raisable

## Required Behavior

- `@field_validator` registers before/after validators on model classes.
- Before validators transform incoming values; after validators run on initialized attributes.
- ValidationError carries structured field errors as an errors list of dicts, and errors[0]["field"] names the failing field.
- The package exposes the required task API paths `featurelifted.field_validator`, `featurelifted.BaseModel`, `featurelifted.ValidationError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pydantic`.
- Forbidden path access: `repo/, pydantic/`.
- Do not implement network access.
- Do not implement full pydantic v2 type system.
- Do not implement JSON schema export.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `@field_validator` registers before/after validators on model classes.
- **B002** — Before validators transform incoming values; after validators run on initialized attributes.
- **B003** — ValidationError carries structured field errors as an errors list of dicts, and errors[0]["field"] names the failing field.
- **B004** — The package exposes the required task API paths `featurelifted.field_validator`, `featurelifted.BaseModel`, `featurelifted.ValidationError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: pydantic.
<!-- featureliftbench:behavior-clauses:end -->
