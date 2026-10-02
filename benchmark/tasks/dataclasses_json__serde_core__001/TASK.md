# FeatureLift Task: Dataclass JSON serde core

Extract a task-scoped subset of `dataclasses_json` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    config,
    dataclass_json,
    DataClassJsonMixin,
    Exclude,
    global_config,
    LetterCase,
    Undefined,
    undefined,
)
```

## Required API Details

- `DataClassJsonMixin()` class constructor
- `LetterCase(new_class_name, /, names, *, module=None, qualname=None, type=None, start=1, boundary=None)` class constructor
  - `LetterCase.CAMEL(string)`
- `Exclude()` class constructor
  - `Exclude.ALWAYS(_)`
- `Undefined(*values)` class constructor
  - `Undefined.RAISE` attribute must exist on instances
- `dataclass_json(_cls: Optional[Type[~T]] = None, *, letter_case: Optional[LetterCase] = None, undefined: Union[str, Undefined, NoneType] = None) -> Union[Callable[[Type[~T]], Type[~T]], Type[~T]]`
- `config(metadata: Optional[dict] = None, *, encoder: Optional[Callable] = None, decoder: Optional[Callable] = None, mm_field: Optional[Any] = None, letter_case: Union[Callable[[str], str], LetterCase, NoneType] = None, undefined: Union[str, Undefined, NoneType] = None, field_name: Optional[str] = None, exclude: Optional[Callable[[~T], bool]] = None) -> Dict[str, dict]`
- `global_config` object must exist
  - `global_config.decoders` attribute must exist
  - `global_config.encoders` attribute must exist
- `undefined` module must be importable
  - `undefined.UndefinedParameterError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: round-trip dataclass instances through JSON and dict payloads. Required observable cases include basic json roundtrip; dict roundtrip; undefined raise on extra keys.
- The extracted feature must support this observable behavior: apply class-level and field-level letter case transforms. Required observable cases include class level camel case; field level camel case; duplicate letter case encoding error.
- The extracted feature must support this observable behavior: exclude fields via config predicates and Exclude helpers. Required observable cases include field name override; exclude always; exclude custom predicate.
- The extracted feature must support this observable behavior: register per-type encoders and decoders via config and global_config. Required observable cases include global config encoder decoder.
- The extracted feature must support this observable behavior: decode nested dataclass fields recursively. Required observable cases include field name override; nested dataclass roundtrip.
- The extracted feature must support this observable behavior: reject unknown keys when undefined=Undefined.RAISE. Required observable cases include undefined raise on extra keys.
- The package exposes the required task API paths `featurelifted.DataClassJsonMixin`, `featurelifted.LetterCase`, `featurelifted.LetterCase.CAMEL`, `featurelifted.Exclude`, `featurelifted.Exclude.ALWAYS`, `featurelifted.Undefined`, `featurelifted.Undefined.RAISE`, `featurelifted.dataclass_json`, `featurelifted.config`, `featurelifted.global_config`, `featurelifted.global_config.decoders`, `featurelifted.global_config.encoders`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `dataclasses_json, dataclasses-json, marshmallow`.
- Do not implement marshmallow schema generation and mm_field validation.
- Do not implement CatchAll undefined INCLUDE mode and schema dump hooks.
- Do not implement upstream tests, docs, CI, and packaging metadata.
- Do not implement original dataclasses_json import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: round-trip dataclass instances through JSON and dict payloads. Required observable cases include basic json roundtrip; dict roundtrip; undefined raise on extra keys.
- **B002** — The extracted feature must support this observable behavior: apply class-level and field-level letter case transforms. Required observable cases include class level camel case; field level camel case; duplicate letter case encoding error.
- **B003** — The extracted feature must support this observable behavior: exclude fields via config predicates and Exclude helpers. Required observable cases include field name override; exclude always; exclude custom predicate.
- **B004** — The extracted feature must support this observable behavior: register per-type encoders and decoders via config and global_config. Required observable cases include global config encoder decoder.
- **B005** — The extracted feature must support this observable behavior: decode nested dataclass fields recursively. Required observable cases include field name override; nested dataclass roundtrip.
- **B006** — The extracted feature must support this observable behavior: reject unknown keys when undefined=Undefined.RAISE. Required observable cases include undefined raise on extra keys.
- **B007** — The package exposes the required task API paths `featurelifted.DataClassJsonMixin`, `featurelifted.LetterCase`, `featurelifted.LetterCase.CAMEL`, `featurelifted.Exclude`, `featurelifted.Exclude.ALWAYS`, `featurelifted.Undefined`, `featurelifted.Undefined.RAISE`, `featurelifted.dataclass_json`, `featurelifted.config`, `featurelifted.global_config`, `featurelifted.global_config.decoders`, `featurelifted.global_config.encoders`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: dataclasses_json, dataclasses-json, marshmallow.
<!-- featureliftbench:behavior-clauses:end -->
