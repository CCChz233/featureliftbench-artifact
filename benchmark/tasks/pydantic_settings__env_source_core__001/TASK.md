# FeatureLift Task: Environment settings source

Extract a task-scoped subset of `pydantic_settings` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    BaseSettings,
    SettingsConfigDict,
    SettingsError,
)
```

## Required API Details

- `BaseSettings(_case_sensitive: 'bool | None' = None, _nested_model_default_partial_update: 'bool | None' = None, _env_prefix: 'str | None' = None, _env_prefix_target: 'EnvPrefixTarget | None' = None, _env_file: 'DotenvType | None' = PosixPath('.'), _env_file_encoding: 'str | None' = None, _env_ignore_empty: 'bool | None' = None, _env_nested_delimiter: 'str | None' = None, _env_nested_max_split: 'int | None' = None, _env_parse_none_str: 'str | None' = None, _env_parse_enums: 'bool | None' = None, _cli_prog_name: 'str | None' = None, _cli_parse_args: 'bool | list[str] | tuple[str, ...] | None' = None, _cli_settings_source: 'CliSettingsSource[Any] | None' = None, _cli_parse_none_str: 'str | None' = None, _cli_hide_none_type: 'bool | None' = None, _cli_avoid_json: 'bool | None' = None, _cli_enforce_required: 'bool | None' = None, _cli_use_class_docs_for_groups: 'bool | None' = None, _cli_exit_on_error: 'bool | None' = None, _cli_prefix: 'str | None' = None, _cli_flag_prefix_char: 'str | None' = None, _cli_implicit_flags: "bool | Literal['dual', 'toggle'] | None" = None, _cli_ignore_unknown_args: 'bool | None' = None, _cli_kebab_case: "bool | Literal['all', 'no_enums'] | None" = None, _cli_shortcuts: 'Mapping[str, str | list[str]] | None' = None, _secrets_dir: 'PathType | None' = None, _build_sources: 'tuple[tuple[PydanticBaseSettingsSource, ...], dict[str, Any]] | None' = None) -> None` class constructor
- `SettingsConfigDict(*args, **kwargs)` class constructor
- `SettingsError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: BaseSettings loads fields from os.environ with env_prefix. Required observable cases include env prefix and nested; parse none str.
- The extracted feature must support this observable behavior: nested models via env_nested_delimiter. Required observable cases include env prefix and nested; parse none str.
- The extracted feature must support this observable behavior: json/complex field parsing and case_sensitive option. Required observable cases include json list env; case sensitive env.
- The extracted feature must support this observable behavior: env_ignore_empty and env_parse_none_str. Required observable cases include json list env; ignore empty env; parse none str.
- The package exposes the required task API paths `featurelifted.BaseSettings`, `featurelifted.SettingsConfigDict`, `featurelifted.SettingsError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pydantic_settings`.
- Do not implement dotenv, yaml/toml/json file sources and cloud secret providers.
- Do not implement CLI settings source and subcommand parsing.
- Do not implement original pydantic_settings import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: BaseSettings loads fields from os.environ with env_prefix. Required observable cases include env prefix and nested; parse none str.
- **B002** — The extracted feature must support this observable behavior: nested models via env_nested_delimiter. Required observable cases include env prefix and nested; parse none str.
- **B003** — The extracted feature must support this observable behavior: json/complex field parsing and case_sensitive option. Required observable cases include json list env; case sensitive env.
- **B004** — The extracted feature must support this observable behavior: env_ignore_empty and env_parse_none_str. Required observable cases include json list env; ignore empty env; parse none str.
- **B005** — The package exposes the required task API paths `featurelifted.BaseSettings`, `featurelifted.SettingsConfigDict`, `featurelifted.SettingsError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: pydantic_settings.
<!-- featureliftbench:behavior-clauses:end -->
