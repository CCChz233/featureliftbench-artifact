# FeatureLift Task: Typed environment variable parsing

Extract a task-scoped subset of `environs` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Env,
    EnvError,
    EnvSealedError,
    EnvValidationError,
    ParserConflictError,
    validate,
    ValidationError,
)
```

## Required API Details

- `Env(*, eager: '_BoolType' = True, expand_vars: '_BoolType' = False, prefix: '_StrType | None' = None)` class constructor
  - `Env.int(self: 'Env', name: 'str', default: 'typing.Any' = Ellipsis, subcast: 'Subcast[_T] | None' = None, *, validate: 'typing.Callable[[typing.Any], typing.Any] | typing.Iterable[typing.Callable[[typing.Any], typing.Any]] | None' = None, **kwargs) -> '_T | None'`
  - `Env.prefixed(self, prefix: '_StrType') -> 'typing.Iterator[Env]'`
  - `Env.seal(self) -> 'None'`
  - `Env.str(self: 'Env', name: 'str', default: 'typing.Any' = Ellipsis, subcast: 'Subcast[_T] | None' = None, *, validate: 'typing.Callable[[typing.Any], typing.Any] | typing.Iterable[typing.Callable[[typing.Any], typing.Any]] | None' = None, **kwargs) -> '_T | None'`
  - `Env.timedelta(self: 'Env', name: 'str', default: 'typing.Any' = Ellipsis, subcast: 'Subcast[_T] | None' = None, *, validate: 'typing.Callable[[typing.Any], typing.Any] | typing.Iterable[typing.Callable[[typing.Any], typing.Any]] | None' = None, **kwargs) -> '_T | None'`
- `EnvError` must be importable and raisable
- `EnvValidationError` must be importable and raisable
- `EnvSealedError` must be importable and raisable
- `ParserConflictError` must be importable and raisable
- `ValidationError` must be importable and raisable
- `validate` module must be importable
  - `validate.Range(min: 'typing.Any' = None, max: 'typing.Any' = None, *, min_inclusive: 'bool' = True, max_inclusive: 'bool' = True, error: 'str | None' = None)` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: typed casting for int, bool, str with defaults and eager errors. Required observable cases include int cast; bool cast; str default when unset; missing required raises; timedelta gep2257 duration.
- The extracted feature must support this observable behavior: marshmallow validate= callables and validators on parsed fields. Required observable cases include marshmallow range validator.
- The extracted feature must support this observable behavior: list and dict env strings with delimiter/subcast preprocessing. Required observable cases include list subcast int; dict subcast values.
- The extracted feature must support this observable behavior: expand_vars ${VAR:-default} substitution in env values. Required observable cases include expand vars with default; expand vars multiple in string.
- The extracted feature must support this observable behavior: constructor and context-manager prefix for env key names. Required observable cases include prefixed context manager.
- The extracted feature must support this observable behavior: deferred validation via eager=False and seal() error aggregation. Required observable cases include deferred seal aggregates errors.
- The extracted feature must support this observable behavior: custom timedelta duration strings via fields.TimeDelta. Required observable cases include timedelta gep2257 duration.
- The package exposes the required task API paths `featurelifted.Env`, `featurelifted.Env.int`, `featurelifted.Env.prefixed`, `featurelifted.Env.seal`, `featurelifted.Env.str`, `featurelifted.Env.timedelta`, `featurelifted.EnvError`, `featurelifted.EnvValidationError`, `featurelifted.EnvSealedError`, `featurelifted.ParserConflictError`, `featurelifted.ValidationError`, `featurelifted.validate`, and 1 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `environs`.
- Do not implement read_env dotenv file loading and FileAwareEnv file indirection.
- Do not implement django URL parsers (dj_db_url, dj_email_url, dj_cache_url).
- Do not implement module-level env singleton, upstream tests, docs, and packaging metadata.
- Do not implement original environs import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: typed casting for int, bool, str with defaults and eager errors. Required observable cases include int cast; bool cast; str default when unset; missing required raises; timedelta gep2257 duration.
- **B002** — The extracted feature must support this observable behavior: marshmallow validate= callables and validators on parsed fields. Required observable cases include marshmallow range validator.
- **B003** — The extracted feature must support this observable behavior: list and dict env strings with delimiter/subcast preprocessing. Required observable cases include list subcast int; dict subcast values.
- **B004** — The extracted feature must support this observable behavior: expand_vars ${VAR:-default} substitution in env values. Required observable cases include expand vars with default; expand vars multiple in string.
- **B005** — The extracted feature must support this observable behavior: constructor and context-manager prefix for env key names. Required observable cases include prefixed context manager.
- **B006** — The extracted feature must support this observable behavior: deferred validation via eager=False and seal() error aggregation. Required observable cases include deferred seal aggregates errors.
- **B007** — The extracted feature must support this observable behavior: custom timedelta duration strings via fields.TimeDelta. Required observable cases include timedelta gep2257 duration.
- **B008** — The package exposes the required task API paths `featurelifted.Env`, `featurelifted.Env.int`, `featurelifted.Env.prefixed`, `featurelifted.Env.seal`, `featurelifted.Env.str`, `featurelifted.Env.timedelta`, `featurelifted.EnvError`, `featurelifted.EnvValidationError`, `featurelifted.EnvSealedError`, `featurelifted.ParserConflictError`, `featurelifted.ValidationError`, `featurelifted.validate`, and 1 listed members with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: environs.
<!-- featureliftbench:behavior-clauses:end -->
