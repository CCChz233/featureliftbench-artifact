# FeatureLift Task: YAML schema rule validation core

Extract a task-scoped subset of `yamale` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    make_schema,
    validate,
    ValidationResult,
    YamaleError,
)
```

## Required API Details

- `make_schema(content: 'str', name: 'str' = 'schema') -> 'Schema'`
- `validate(schema: 'Schema', data: 'list[tuple[dict, str]]', strict: 'bool' = True, _raise_error: 'bool' = True)`
- `ValidationResult(data_name: 'str', schema_name: 'str', errors: 'list[str]' = <factory>) -> None` class constructor
- `YamaleError` must be importable and raisable

## Required Behavior

- `make_schema` parses one or more YAML documents; later documents provide `include` targets.
- Validate maps, lists, primitive types, optional fields, and included schemas.
- `strict=True` rejects unexpected keys; non-strict bool validation may accept common string/int aliases.
- `validate` returns `ValidationResult` objects and raises `YamaleError` when invalid and `_raise_error=True`.
- The package exposes the required task API paths `featurelifted.make_schema`, `featurelifted.validate`, `featurelifted.ValidationResult`, `featurelifted.YamaleError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `yamale`.
- Forbidden path access: `repo/, yamale/`.
- Do not implement network access.
- Do not implement CLI.
- Do not implement filesystem loading.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `make_schema` parses one or more YAML documents; later documents provide `include` targets.
- **B002** — Validate maps, lists, primitive types, optional fields, and included schemas.
- **B003** — `strict=True` rejects unexpected keys; non-strict bool validation may accept common string/int aliases.
- **B004** — `validate` returns `ValidationResult` objects and raises `YamaleError` when invalid and `_raise_error=True`.
- **B005** — The package exposes the required task API paths `featurelifted.make_schema`, `featurelifted.validate`, `featurelifted.ValidationResult`, `featurelifted.YamaleError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: yamale.
<!-- featureliftbench:behavior-clauses:end -->
