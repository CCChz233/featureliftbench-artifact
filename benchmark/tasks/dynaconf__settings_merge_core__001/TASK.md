# FeatureLift Task: Layered settings merge

Extract a task-scoped subset of `dynaconf` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Dynaconf,
    object_merge,
)
```

## Required API Details

- `Dynaconf(wrapped=None, **kwargs)` class constructor
  - `Dynaconf.BAR` attribute must exist on instances
  - `Dynaconf.FOO` attribute must exist on instances
  - `Dynaconf.HOST` attribute must exist on instances
  - `Dynaconf.LIST` attribute must exist on instances
  - `Dynaconf.PORT` attribute must exist on instances
  - `Dynaconf.setenv(env=None, clean=True, silent=True, filename=None)`
- `object_merge(old: 'Any', new: 'Any', unique: 'bool' = False, full_path: 'Optional[list[str]]' = None, list_merge: 'ListMergeOptions' = 'merge') -> 'Any'`

## Required Behavior

- The extracted feature must support this observable behavior: recursive object_merge with list_merge shallow/deep/merge modes. Required observable cases include object merge nested dict; object merge list shallow; object merge list deep path.
- The extracted feature must support this observable behavior: Dynaconf loads layered TOML settings files with environment sections. Required observable cases include dynaconf toml and env override; layered toml environments; merge multiple settings files.
- The extracted feature must support this observable behavior: envvar_prefix overrides nested keys with precedence over file values. Required observable cases include object merge list shallow.
- The extracted feature must support this observable behavior: merge_enabled combines multiple settings files. Required observable cases include merge multiple settings files.
- The package exposes the required task API paths `featurelifted.Dynaconf`, `featurelifted.Dynaconf.BAR`, `featurelifted.Dynaconf.FOO`, `featurelifted.Dynaconf.HOST`, `featurelifted.Dynaconf.LIST`, `featurelifted.Dynaconf.PORT`, `featurelifted.Dynaconf.setenv`, `featurelifted.object_merge` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `dynaconf`.
- Do not implement Flask/Django extensions and CLI.
- Do not implement vault/redis external loaders.
- Do not implement typed settings subsystem and validators beyond merge.
- Do not implement original dynaconf import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: recursive object_merge with list_merge shallow/deep/merge modes. Required observable cases include object merge nested dict; object merge list shallow; object merge list deep path.
- **B002** — The extracted feature must support this observable behavior: Dynaconf loads layered TOML settings files with environment sections. Required observable cases include dynaconf toml and env override; layered toml environments; merge multiple settings files.
- **B003** — The extracted feature must support this observable behavior: envvar_prefix overrides nested keys with precedence over file values. Required observable cases include object merge list shallow.
- **B004** — The extracted feature must support this observable behavior: merge_enabled combines multiple settings files. Required observable cases include merge multiple settings files.
- **B005** — The package exposes the required task API paths `featurelifted.Dynaconf`, `featurelifted.Dynaconf.BAR`, `featurelifted.Dynaconf.FOO`, `featurelifted.Dynaconf.HOST`, `featurelifted.Dynaconf.LIST`, `featurelifted.Dynaconf.PORT`, `featurelifted.Dynaconf.setenv`, `featurelifted.object_merge` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: dynaconf.
<!-- featureliftbench:behavior-clauses:end -->
