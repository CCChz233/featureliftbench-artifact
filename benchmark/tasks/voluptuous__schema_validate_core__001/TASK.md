# FeatureLift Task: Schema validation core

Extract a task-scoped subset of `voluptuous` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    All,
    Any,
    Coerce,
    In,
    Invalid,
    MultipleInvalid,
    Optional,
    Required,
    Schema,
    SchemaError,
)
```

## Required API Details

- `Schema(schema: 'Schemable', required: 'bool' = False, extra: 'int' = 0) -> 'None'` class constructor
- `Required(schema: 'Schemable', msg: 'typing.Optional[str]' = None, default: 'typing.Any' = ..., description: 'typing.Any | None' = None) -> 'None'` class constructor
- `Optional(schema: 'Schemable', msg: 'typing.Optional[str]' = None, default: 'typing.Any' = ..., description: 'typing.Any | None' = None) -> 'None'` class constructor
- `All(*validators, msg=None, required=False, discriminant=None, **kwargs) -> 'None'` class constructor
- `Any(*validators, msg=None, required=False, discriminant=None, **kwargs) -> 'None'` class constructor
- `In(container: 'typing.Container | typing.Iterable', msg: 'typing.Optional[str]' = None) -> 'None'` class constructor
- `Coerce(type: 'typing.Union[type, typing.Callable]', msg: 'typing.Optional[str]' = None) -> 'None'` class constructor
- `Invalid` must be importable and raisable
- `MultipleInvalid` must be importable and raisable
- `SchemaError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: declare Schema with Required and Optional markers. Required observable cases include schema required field; optional missing key; nested schema validation.
- The extracted feature must support this observable behavior: validate dict payloads with type and nested schema matching. Required observable cases include basic type validation; nested schema validation.
- The extracted feature must support this observable behavior: compose All, Any, and In validators with Coerce. Required observable cases include all any in and coerce.
- The extracted feature must support this observable behavior: aggregate validation failures as MultipleInvalid with error paths. Required observable cases include basic type validation; multiple invalid error paths.
- The package exposes the required task API paths `featurelifted.Schema`, `featurelifted.Required`, `featurelifted.Optional`, `featurelifted.All`, `featurelifted.Any`, `featurelifted.In`, `featurelifted.Coerce`, `featurelifted.Invalid`, `featurelifted.MultipleInvalid`, `featurelifted.SchemaError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `voluptuous`.
- Do not implement humanize_error and CLI helpers.
- Do not implement Email, Url, File, and other heavyweight validators.
- Do not implement original voluptuous import at runtime.
- Do not implement upstream packaging and bin scripts.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: declare Schema with Required and Optional markers. Required observable cases include schema required field; optional missing key; nested schema validation.
- **B002** — The extracted feature must support this observable behavior: validate dict payloads with type and nested schema matching. Required observable cases include basic type validation; nested schema validation.
- **B003** — The extracted feature must support this observable behavior: compose All, Any, and In validators with Coerce. Required observable cases include all any in and coerce.
- **B004** — The extracted feature must support this observable behavior: aggregate validation failures as MultipleInvalid with error paths. Required observable cases include basic type validation; multiple invalid error paths.
- **B005** — The package exposes the required task API paths `featurelifted.Schema`, `featurelifted.Required`, `featurelifted.Optional`, `featurelifted.All`, `featurelifted.Any`, `featurelifted.In`, `featurelifted.Coerce`, `featurelifted.Invalid`, `featurelifted.MultipleInvalid`, `featurelifted.SchemaError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: voluptuous.
<!-- featureliftbench:behavior-clauses:end -->
