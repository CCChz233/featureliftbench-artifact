# FeatureLift Task: Structure/unstructure core

Extract a task-scoped subset of `cattrs` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Converter,
    errors,
    gen,
    structure,
    unstructure,
)
```

## Required API Details

- `Converter(dict_factory: Callable[[], Any] = <class 'dict'>, unstruct_strat: UnstructureStrategy = <UnstructureStrategy.AS_DICT: 'asdict'>, omit_if_default: bool = False, forbid_extra_keys: bool = False, type_overrides: collections.abc.Mapping[typing.Type, AttributeOverride] = {}, unstruct_collection_overrides: collections.abc.Mapping[typing.Type, typing.Callable] = {}, prefer_attrib_converters: bool = False, detailed_validation: bool = True, unstructure_fallback_factory: Callable[[Any], Callable[[Any], Any]] = <function Converter.<lambda>>, structure_fallback_factory: Callable[[Any], Callable[[Any, Any], Any]] = <function Converter.<lambda>>)` class constructor
  - `Converter.structure(self, obj: Any, cl: Type[~T]) -> ~T`
  - `Converter.register_structure_hook(self, cl: Any, func: Callable[[Any, Any], Any]) -> None`
  - `Converter.register_unstructure_hook(self, cls: Any, func: Callable[[Any], Any]) -> None`
  - `Converter.unstructure(self, obj: Any, unstructure_as: Any = None) -> Any`
- `structure(obj: Any, cl: Type[~T]) -> ~T`
- `unstructure(obj: Any, unstructure_as: Any = None) -> Any`
- `errors` module must be importable
  - `errors.ClassValidationError` must be importable and raisable
  - `errors.ForbiddenExtraKeysError` must be importable and raisable
- `gen` module must be importable
  - `gen.make_dict_structure_fn(cl: 'type[T]', converter: 'BaseConverter', _cattrs_forbid_extra_keys: "bool | Literal['from_converter']" = 'from_converter', _cattrs_use_linecache: 'bool' = True, _cattrs_prefer_attrib_converters: 'bool' = False, _cattrs_detailed_validation: "bool | Literal['from_converter']" = 'from_converter', _cattrs_use_alias: 'bool' = False, _cattrs_include_init_false: 'bool' = False, **kwargs: 'AttributeOverride') -> 'DictStructureFn[T]'`
  - `gen.make_dict_unstructure_fn(cl: 'type[T]', converter: 'BaseConverter', _cattrs_omit_if_default: 'bool' = False, _cattrs_use_linecache: 'bool' = True, _cattrs_use_alias: 'bool' = False, _cattrs_include_init_false: 'bool' = False, **kwargs: 'AttributeOverride') -> 'Callable[[T], dict[str, Any]]'`
  - `gen.override(omit_if_default: 'bool | None' = None, rename: 'str | None' = None, omit: 'bool | None' = None, struct_hook: 'Callable[[Any, Any], Any] | None' = None, unstruct_hook: 'Callable[[Any], Any] | None' = None) -> 'AttributeOverride'`

## Required Behavior

- The extracted feature must support this observable behavior: round-trip attrs and dataclass instances through dict payloads. Required observable cases include nested attrs and dataclass.
- The extracted feature must support this observable behavior: structure and unstructure nested mappings and sequences. Required observable cases include attrs roundtrip; dataclass roundtrip; nested attrs and dataclass; optional none field.
- The extracted feature must support this observable behavior: register custom dict structure/unstructure hooks via gen helpers. Required observable cases include attrs roundtrip; dataclass roundtrip; module level helpers; structure hook rename override; optional none field.
- The extracted feature must support this observable behavior: apply per-field rename and omit_if_default overrides. Required observable cases include structure hook rename override; unstructure omit if default.
- The extracted feature must support this observable behavior: reject extra dict keys when forbid_extra_keys is enabled. Required observable cases include forbid extra keys.
- The package exposes the required task API paths `featurelifted.Converter`, `featurelifted.Converter.structure`, `featurelifted.Converter.register_structure_hook`, `featurelifted.Converter.register_unstructure_hook`, `featurelifted.Converter.unstructure`, `featurelifted.structure`, `featurelifted.unstructure`, `featurelifted.errors`, `featurelifted.errors.ClassValidationError`, `featurelifted.errors.ForbiddenExtraKeysError`, `featurelifted.gen`, `featurelifted.gen.make_dict_structure_fn`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `cattrs`.
- Do not implement preconf JSON/YAML/msgpack adapters and third-party codec integrations.
- Do not implement strategies package for union/subclass hook registry explosion.
- Do not implement GenConverter code generation and transform_error validation helpers.
- Do not implement upstream tests, docs, benchmarks, and packaging metadata.
- Do not implement original cattrs import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: round-trip attrs and dataclass instances through dict payloads. Required observable cases include nested attrs and dataclass.
- **B002** — The extracted feature must support this observable behavior: structure and unstructure nested mappings and sequences. Required observable cases include attrs roundtrip; dataclass roundtrip; nested attrs and dataclass; optional none field.
- **B003** — The extracted feature must support this observable behavior: register custom dict structure/unstructure hooks via gen helpers. Required observable cases include attrs roundtrip; dataclass roundtrip; module level helpers; structure hook rename override; optional none field.
- **B004** — The extracted feature must support this observable behavior: apply per-field rename and omit_if_default overrides. Required observable cases include structure hook rename override; unstructure omit if default.
- **B005** — The extracted feature must support this observable behavior: reject extra dict keys when forbid_extra_keys is enabled. Required observable cases include forbid extra keys.
- **B006** — The package exposes the required task API paths `featurelifted.Converter`, `featurelifted.Converter.structure`, `featurelifted.Converter.register_structure_hook`, `featurelifted.Converter.register_unstructure_hook`, `featurelifted.Converter.unstructure`, `featurelifted.structure`, `featurelifted.unstructure`, `featurelifted.errors`, `featurelifted.errors.ClassValidationError`, `featurelifted.errors.ForbiddenExtraKeysError`, `featurelifted.gen`, `featurelifted.gen.make_dict_structure_fn`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: cattrs.
<!-- featureliftbench:behavior-clauses:end -->
