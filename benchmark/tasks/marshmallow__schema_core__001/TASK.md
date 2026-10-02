# FeatureLift Task: Schema load and dump

Extract a task-scoped subset of `marshmallow` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    decorators,
    EXCLUDE,
    fields,
    RAISE,
    Schema,
    ValidationError,
)
```

## Required API Details

- `Schema(*, only: 'types.StrSequenceOrSet | None' = None, exclude: 'types.StrSequenceOrSet' = (), many: 'bool | None' = None, load_only: 'types.StrSequenceOrSet' = (), dump_only: 'types.StrSequenceOrSet' = (), partial: 'bool | types.StrSequenceOrSet | None' = None, unknown: 'types.UnknownOption | None' = None)` class constructor
  - `Schema.load(self, data: 'Mapping[str, typing.Any] | Sequence[Mapping[str, typing.Any]]', *, many: 'bool | None' = None, partial: 'bool | types.StrSequenceOrSet | None' = None, unknown: 'types.UnknownOption | None' = None)`
- `fields` module must be importable
  - `fields.Int(*, strict: 'bool' = False, as_string: 'bool' = False, **kwargs: 'Unpack[_BaseFieldKwargs]')` class constructor
  - `fields.List(cls_or_instance: 'Field[_InternalT] | type[Field[_InternalT]]', **kwargs: 'Unpack[_BaseFieldKwargs]')` class constructor
  - `fields.Nested(nested: 'Schema | SchemaMeta | str | dict[str, Field] | typing.Callable[[], Schema | SchemaMeta | str | dict[str, Field]]', *, only: 'types.StrSequenceOrSet | None' = None, exclude: 'types.StrSequenceOrSet' = (), many: 'bool | None' = None, unknown: 'types.UnknownOption | None' = None, **kwargs: 'Unpack[_BaseFieldKwargs]')` class constructor
  - `fields.Str(*, load_default: 'typing.Any' = <marshmallow.missing>, dump_default: 'typing.Any' = <marshmallow.missing>, data_key: 'str | None' = None, attribute: 'str | None' = None, validate: 'types.Validator | typing.Iterable[types.Validator] | None' = None, pre_load: 'types.PreLoadCallable | typing.Iterable[types.PreLoadCallable] | None' = None, post_load: 'types.PostLoadCallable | typing.Iterable[types.PostLoadCallable] | None' = None, required: 'bool' = False, allow_none: 'bool | None' = None, load_only: 'bool' = False, dump_only: 'bool' = False, error_messages: 'types.ErrorMessages | None' = None, metadata: 'typing.Mapping[str, typing.Any] | None' = None) -> 'None'` class constructor
- `ValidationError` must be importable and raisable
- `EXCLUDE` constant must exist
- `RAISE` constant must exist
- `decorators` module must be importable
  - `decorators.post_load(fn: 'typing.Callable[..., typing.Any] | None' = None, *, pass_collection: 'bool' = False, pass_original: 'bool' = False) -> 'typing.Callable[..., typing.Any]'`
  - `decorators.validates_schema(fn: 'typing.Callable[..., typing.Any] | None' = None, *, pass_collection: 'bool' = False, pass_original: 'bool' = False, skip_on_field_errors: 'bool' = True) -> 'typing.Callable[..., typing.Any]'`

## Required Behavior

- The extracted feature must support this observable behavior: declare Schema subclasses with typed fields. Required observable cases include unknown exclude post load and nested errors.
- The extracted feature must support this observable behavior: load dict payloads with validation and nested schemas. Required observable cases include load dump nested schema; unknown exclude post load and nested errors.
- The extracted feature must support this observable behavior: dump objects to dicts with field selection. Required observable cases include unknown exclude post load and nested errors.
- The extracted feature must support this observable behavior: handle unknown=EXCLUDE and partial load validation errors. Required observable cases include unknown exclude post load and nested errors; many dump partial and raise unknown.
- The package exposes the required task API paths `featurelifted.Schema`, `featurelifted.Schema.load`, `featurelifted.fields`, `featurelifted.fields.Int`, `featurelifted.fields.List`, `featurelifted.fields.Nested`, `featurelifted.fields.Str`, `featurelifted.ValidationError`, `featurelifted.EXCLUDE`, `featurelifted.RAISE`, `featurelifted.decorators`, `featurelifted.decorators.post_load`, and 1 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `marshmallow`.
- Do not implement flask-smorest and web framework integrations.
- Do not implement original project tests and packaging metadata.
- Do not implement schema class registry across entry points.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: declare Schema subclasses with typed fields. Required observable cases include unknown exclude post load and nested errors.
- **B002** — The extracted feature must support this observable behavior: load dict payloads with validation and nested schemas. Required observable cases include load dump nested schema; unknown exclude post load and nested errors.
- **B003** — The extracted feature must support this observable behavior: dump objects to dicts with field selection. Required observable cases include unknown exclude post load and nested errors.
- **B004** — The extracted feature must support this observable behavior: handle unknown=EXCLUDE and partial load validation errors. Required observable cases include unknown exclude post load and nested errors; many dump partial and raise unknown.
- **B005** — The package exposes the required task API paths `featurelifted.Schema`, `featurelifted.Schema.load`, `featurelifted.fields`, `featurelifted.fields.Int`, `featurelifted.fields.List`, `featurelifted.fields.Nested`, `featurelifted.fields.Str`, `featurelifted.ValidationError`, `featurelifted.EXCLUDE`, `featurelifted.RAISE`, `featurelifted.decorators`, `featurelifted.decorators.post_load`, and 1 listed members with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: marshmallow.
<!-- featureliftbench:behavior-clauses:end -->
