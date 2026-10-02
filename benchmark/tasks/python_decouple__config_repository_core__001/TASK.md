# FeatureLift Task: Environment-backed configuration repository

Extract a task-scoped subset of `python_decouple` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Choices,
    Config,
    Csv,
    RepositoryDict,
    RepositoryEnv,
    UndefinedValueError,
)
```

## Required API Details

- `Choices(choices, cast=<class 'str'>)` class constructor
- `Config(repository, environ=None)` class constructor
- `Csv(cast=<class 'str'>, delimiter=',', strip=' ')` class constructor
- `RepositoryDict(data)` class constructor
- `RepositoryEnv(source)` class constructor
- `UndefinedValueError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: environment variables override repository values. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- The extracted feature must support this observable behavior: .env quoted-value and comment parsing. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- The extracted feature must support this observable behavior: required and default value behavior. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- The extracted feature must support this observable behavior: bool, int, float, Csv, and Choices casting. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- The package exposes the required task API paths `featurelifted.Choices`, `featurelifted.Config`, `featurelifted.Csv`, `featurelifted.RepositoryDict`, `featurelifted.RepositoryEnv`, `featurelifted.UndefinedValueError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `python_decouple`.
- Forbidden path access: `repo/, python_decouple/`.
- Do not implement INI files.
- Do not implement AutoConfig directory search.
- Do not implement encoding auto-detection.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: environment variables override repository values. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- **B002** — The extracted feature must support this observable behavior: .env quoted-value and comment parsing. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- **B003** — The extracted feature must support this observable behavior: required and default value behavior. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- **B004** — The extracted feature must support this observable behavior: bool, int, float, Csv, and Choices casting. Required observable cases include precedence defaults and casts; csv cast; env file quotes comments and empty; choices and float.
- **B005** — The package exposes the required task API paths `featurelifted.Choices`, `featurelifted.Config`, `featurelifted.Csv`, `featurelifted.RepositoryDict`, `featurelifted.RepositoryEnv`, `featurelifted.UndefinedValueError` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: python_decouple.
<!-- featureliftbench:behavior-clauses:end -->
