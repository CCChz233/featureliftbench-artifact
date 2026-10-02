# FeatureLift Task: JSON Schema Draft 2020-12 validation core

Extract a task-scoped subset of `jsonschema` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Draft202012Validator,
    FormatChecker,
    SchemaError,
    validate,
    ValidationError,
)
```

## Required API Details

- `Draft202012Validator(schema: 'referencing.jsonschema.Schema', resolver=None, format_checker: '_format.FormatChecker | None' = None, *, registry: 'referencing.jsonschema.SchemaRegistry' = <Registry (20 resources)>, _resolver=None) -> None` class constructor
  - `Draft202012Validator.check_schema(schema, format_checker=<unset>)`
  - `Draft202012Validator.is_valid(self, instance, _schema=None)`
  - `Draft202012Validator.iter_errors(self, instance, _schema=None)`
- `validate(instance, schema, cls=None, *args, **kwargs)`
- `ValidationError` must be importable and raisable
- `SchemaError` must be importable and raisable
- `FormatChecker(formats: 'typing.Iterable[str] | None' = None)` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: validate object, array, string, integer, number, boolean, and null types. Required observable cases include validate object required properties and minimum; oneof and const keyword.
- The extracted feature must support this observable behavior: support required, properties, additionalProperties, minimum, minLength, pattern, enum, anyOf, oneOf, and allOf. Required observable cases include validate object required properties and minimum; oneof and const keyword.
- The extracted feature must support this observable behavior: iterate ValidationError objects with path, schema_path, validator, validator_value, and message. Required observable cases include iter errors exposes paths and validity; nested errors paths combinators and messages.
- The extracted feature must support this observable behavior: perform format validation when a FormatChecker is provided. Required observable cases include format checker schema errors and additional properties.
- The extracted feature must support this observable behavior: validate schemas and raise SchemaError for invalid schemas. Required observable cases include format checker schema errors and additional properties.
- The package exposes the required task API paths `featurelifted.Draft202012Validator`, `featurelifted.Draft202012Validator.check_schema`, `featurelifted.Draft202012Validator.is_valid`, `featurelifted.Draft202012Validator.iter_errors`, `featurelifted.validate`, `featurelifted.ValidationError`, `featurelifted.SchemaError`, `featurelifted.FormatChecker` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jsonschema`.
- Do not implement remote reference retrieval over network.
- Do not implement CLI tooling.
- Do not implement benchmark suites and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: validate object, array, string, integer, number, boolean, and null types. Required observable cases include validate object required properties and minimum; oneof and const keyword.
- **B002** — The extracted feature must support this observable behavior: support required, properties, additionalProperties, minimum, minLength, pattern, enum, anyOf, oneOf, and allOf. Required observable cases include validate object required properties and minimum; oneof and const keyword.
- **B003** — The extracted feature must support this observable behavior: iterate ValidationError objects with path, schema_path, validator, validator_value, and message. Required observable cases include iter errors exposes paths and validity; nested errors paths combinators and messages.
- **B004** — The extracted feature must support this observable behavior: perform format validation when a FormatChecker is provided. Required observable cases include format checker schema errors and additional properties.
- **B005** — The extracted feature must support this observable behavior: validate schemas and raise SchemaError for invalid schemas. Required observable cases include format checker schema errors and additional properties.
- **B006** — The package exposes the required task API paths `featurelifted.Draft202012Validator`, `featurelifted.Draft202012Validator.check_schema`, `featurelifted.Draft202012Validator.is_valid`, `featurelifted.Draft202012Validator.iter_errors`, `featurelifted.validate`, `featurelifted.ValidationError`, `featurelifted.SchemaError`, `featurelifted.FormatChecker` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: jsonschema.
<!-- featureliftbench:behavior-clauses:end -->
