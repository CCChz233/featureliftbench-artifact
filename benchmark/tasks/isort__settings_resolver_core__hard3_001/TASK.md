# FeatureLift Task: Settings/profile resolution and skip matching

Extract a task-scoped subset of `isort` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    find_config,
    ProfileDoesNotExist,
    resolve_from_path,
    resolve_settings,
    Settings,
    should_skip,
    UnsupportedSettings,
)
```

## Required API Details

- `ProfileDoesNotExist` must be importable and raisable
- `UnsupportedSettings` must be importable and raisable
- `Settings(line_length: 'int' = 79, multi_line_output: 'int' = 0, include_trailing_comma: 'bool' = False, split_on_trailing_comma: 'bool' = False, force_grid_wrap: 'int' = 0, use_parentheses: 'bool' = False, ensure_newline_before_comments: 'bool' = False, combine_as_imports: 'bool' = False, force_single_line: 'bool' = False, force_sort_within_sections: 'bool' = False, lexicographical: 'bool' = False, order_by_type: 'bool' = True, group_by_package: 'bool' = False, skip: 'frozenset[str]' = frozenset({'.pants.d', '_build', '.mypy_cache', '.svn', '.eggs', '.git', '.direnv', '.hg', 'node_modules', 'dist', '.tox', '.bzr', '.venv', 'buck-out', '.nox', 'build'}), extend_skip: 'frozenset[str]' = frozenset(), skip_glob: 'frozenset[str]' = frozenset(), extend_skip_glob: 'frozenset[str]' = frozenset(), src_paths: 'tuple[Path, ...]' = (), directory: 'Path' = <factory>, profile: 'str' = '', source: 'str' = 'defaults', sources: 'tuple[str, ...]' = ('defaults',)) -> None` class constructor
  - `Settings.line_length` attribute must exist on instances
  - `Settings.src_paths` attribute must exist on instances
- `resolve_settings(config_files=(), profile: 'str | None' = None, overrides: 'dict[str, Any] | None' = None) -> 'Settings'`
- `resolve_from_path(start_path: 'str | Path', profile: 'str | None' = None, overrides: 'dict[str, Any] | None' = None) -> 'Settings'`
- `find_config(start_path: 'str | Path') -> 'Path | None'`
- `should_skip(path: 'str | Path', settings: 'Settings') -> 'bool'`
- `Settings.is_skipped(self, path: 'str | Path') -> 'bool'`

## Required Behavior

- When config files, profile, and runtime overrides are supplied, resolve_settings returns a Settings object whose fields reflect defaults, then profile, then config files, then overrides.
- When resolve_from_path is called from a file path, it discovers the nearest applicable config and returns Settings resolved from that discovery chain.
- When find_config is called from a start path, it returns the nearest config file path used by isort or None when no config exists.
- When should_skip is called with a path and Settings, it returns True only for paths matching explicit skip names or glob patterns.
- When Settings.is_skipped is called, it applies the same skip-name and glob rules as should_skip for that Settings instance.
- When black, django, or google profiles are selected, the resulting Settings expose the profile-specific defaults expected by isort.
- When pyproject.toml, setup.cfg, tox.ini, .isort.cfg, or .editorconfig sections are present, their isort-relevant options are parsed into Settings.
- When runtime overrides are provided, they override profile and config-file values in the resolved Settings object.
- When src_paths are configured, they are expanded relative to the config file directory in the resolved Settings object.
- When skip, extend_skip, skip_glob, or extend_skip_glob are configured, the effective skip rules merge extend lists and still allow existing non-matching files to remain unskipped.
- The package exposes the required task API paths `featurelifted.ProfileDoesNotExist`, `featurelifted.UnsupportedSettings`, `featurelifted.Settings`, `featurelifted.Settings.line_length`, `featurelifted.Settings.src_paths`, `featurelifted.resolve_settings`, `featurelifted.resolve_from_path`, `featurelifted.find_config`, `featurelifted.should_skip`, `featurelifted.Settings.is_skipped` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `isort`.
- Forbidden path access: `repo/, isort/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement import sorting.
- Do not implement formatter internals.
- Do not implement CLI.
- Do not implement git ls-files integration.
- Do not implement entry point plugins.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When config files, profile, and runtime overrides are supplied, resolve_settings returns a Settings object whose fields reflect defaults, then profile, then config files, then overrides.
- **B002** — When resolve_from_path is called from a file path, it discovers the nearest applicable config and returns Settings resolved from that discovery chain.
- **B003** — When find_config is called from a start path, it returns the nearest config file path used by isort or None when no config exists.
- **B004** — When should_skip is called with a path and Settings, it returns True only for paths matching explicit skip names or glob patterns.
- **B005** — When Settings.is_skipped is called, it applies the same skip-name and glob rules as should_skip for that Settings instance.
- **B006** — When black, django, or google profiles are selected, the resulting Settings expose the profile-specific defaults expected by isort.
- **B007** — When pyproject.toml, setup.cfg, tox.ini, .isort.cfg, or .editorconfig sections are present, their isort-relevant options are parsed into Settings.
- **B008** — When runtime overrides are provided, they override profile and config-file values in the resolved Settings object.
- **B009** — When src_paths are configured, they are expanded relative to the config file directory in the resolved Settings object.
- **B010** — When skip, extend_skip, skip_glob, or extend_skip_glob are configured, the effective skip rules merge extend lists and still allow existing non-matching files to remain unskipped.
- **B011** — The package exposes the required task API paths `featurelifted.ProfileDoesNotExist`, `featurelifted.UnsupportedSettings`, `featurelifted.Settings`, `featurelifted.Settings.line_length`, `featurelifted.Settings.src_paths`, `featurelifted.resolve_settings`, `featurelifted.resolve_from_path`, `featurelifted.find_config`, `featurelifted.should_skip`, `featurelifted.Settings.is_skipped` with the kinds and callable signatures listed in this contract.
- **B012** — The submitted package does not import forbidden upstream packages: isort.
<!-- featureliftbench:behavior-clauses:end -->
