# FeatureLift Task: BaseModel validation and structured ValidationError core

Extract a task-scoped subset of `pydantic` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    BaseModel,
    Extra,
    Field,
    root_validator,
    ValidationError,
    validator,
)
```

## Required API Details

- `BaseModel() -> None` class constructor
  - `BaseModel.parse_obj(obj: Any) -> 'Model'`
- `Field(default: Any = PydanticUndefined, *, default_factory: Optional[Callable[[], Any]] = None, alias: Optional[str] = None, title: Optional[str] = None, description: Optional[str] = None, exclude: Union[ForwardRef('AbstractSetIntStr'), ForwardRef('MappingIntStrAny'), Any, NoneType] = None, include: Union[ForwardRef('AbstractSetIntStr'), ForwardRef('MappingIntStrAny'), Any, NoneType] = None, const: Optional[bool] = None, gt: Optional[float] = None, ge: Optional[float] = None, lt: Optional[float] = None, le: Optional[float] = None, multiple_of: Optional[float] = None, allow_inf_nan: Optional[bool] = None, max_digits: Optional[int] = None, decimal_places: Optional[int] = None, min_items: Optional[int] = None, max_items: Optional[int] = None, unique_items: Optional[bool] = None, min_length: Optional[int] = None, max_length: Optional[int] = None, allow_mutation: bool = True, regex: Optional[str] = None, discriminator: Optional[str] = None, repr: bool = True, **extra: Any) -> Any`
- `ValidationError` must be importable and raisable
- `validator(*fields: str, pre: bool = False, each_item: bool = False, always: bool = False, check_fields: bool = True, whole: Optional[bool] = None, allow_reuse: bool = False) -> Callable[[Callable[..., Any]], ForwardRef('AnyClassMethod')]`
- `root_validator(_func: Optional[Callable[..., Any]] = None, *, pre: bool = False, allow_reuse: bool = False, skip_on_failure: bool = False) -> Union[ForwardRef('AnyClassMethod'), Callable[[Callable[..., Any]], ForwardRef('AnyClassMethod')]]`
- `Extra(*values)` class constructor
  - `Extra.forbid` attribute must exist on instances

## Required Behavior

- The extracted feature must support this observable behavior: declare BaseModel subclasses and parse dict input. Required observable cases include simple model parses fields; missing required field raises; parse obj classmethod; validator pre runs before type check.
- The extracted feature must support this observable behavior: field validators with pre/each_item semantics. Required observable cases include field validator runs; validator pre runs before type check.
- The extracted feature must support this observable behavior: root_validator whole-model checks. Required observable cases include root validator rejects invalid combo.
- The extracted feature must support this observable behavior: Config.extra forbid for unknown keys. Required observable cases include extra forbid rejects unknown keys.
- The extracted feature must support this observable behavior: ValidationError.errors() with loc/type/msg for nested models. Required observable cases include missing required field raises; nested validation error loc paths; multiple errors collected.
- The package exposes the required task API paths `featurelifted.BaseModel`, `featurelifted.BaseModel.parse_obj`, `featurelifted.Field`, `featurelifted.ValidationError`, `featurelifted.validator`, `featurelifted.root_validator`, `featurelifted.Extra`, `featurelifted.Extra.forbid` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pydantic`.
- Do not implement JSON Schema generation and schema_json.
- Do not implement network/email/DSN types and BaseSettings.
- Do not implement dataclasses bridge, validate_arguments, mypy plugin.
- Do not implement original pydantic package import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: declare BaseModel subclasses and parse dict input. Required observable cases include simple model parses fields; missing required field raises; parse obj classmethod; validator pre runs before type check.
- **B002** — The extracted feature must support this observable behavior: field validators with pre/each_item semantics. Required observable cases include field validator runs; validator pre runs before type check.
- **B003** — The extracted feature must support this observable behavior: root_validator whole-model checks. Required observable cases include root validator rejects invalid combo.
- **B004** — The extracted feature must support this observable behavior: Config.extra forbid for unknown keys. Required observable cases include extra forbid rejects unknown keys.
- **B005** — The extracted feature must support this observable behavior: ValidationError.errors() with loc/type/msg for nested models. Required observable cases include missing required field raises; nested validation error loc paths; multiple errors collected.
- **B006** — The package exposes the required task API paths `featurelifted.BaseModel`, `featurelifted.BaseModel.parse_obj`, `featurelifted.Field`, `featurelifted.ValidationError`, `featurelifted.validator`, `featurelifted.root_validator`, `featurelifted.Extra`, `featurelifted.Extra.forbid` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pydantic.
<!-- featureliftbench:behavior-clauses:end -->
