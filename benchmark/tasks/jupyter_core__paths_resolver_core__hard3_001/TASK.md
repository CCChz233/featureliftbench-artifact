# FeatureLift Task: Jupyter config/data/runtime path resolution

Extract a task-scoped subset of `jupyter_core` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    jupyter_config_dir,
    jupyter_config_path,
    jupyter_data_dir,
    jupyter_path,
    jupyter_runtime_dir,
)
```

## Required API Details

- `jupyter_config_dir(env: 'Mapping[str, str] | None' = None, home: 'str | None' = None, platform: 'str' = 'linux') -> 'str'`
- `jupyter_config_path(env: 'Mapping[str, str] | None' = None, home: 'str | None' = None, platform: 'str' = 'linux', sys_prefix: 'str' = '/usr', user_site_base: 'str | None' = None, enable_user_site: 'bool' = True) -> 'list[str]'`
- `jupyter_data_dir(env: 'Mapping[str, str] | None' = None, home: 'str | None' = None, platform: 'str' = 'linux') -> 'str'`
- `jupyter_path(*subdirs: 'str', env: 'Mapping[str, str] | None' = None, home: 'str | None' = None, platform: 'str' = 'linux', sys_prefix: 'str' = '/usr', user_site_base: 'str | None' = None, enable_user_site: 'bool' = True) -> 'list[str]'`
- `jupyter_runtime_dir(env: 'Mapping[str, str] | None' = None, home: 'str | None' = None, platform: 'str' = 'linux') -> 'str'`

## Required Behavior

- When JUPYTER_CONFIG_PATH or JUPYTER_PATH is set, its entries are ordered ahead of the applicable default search paths.
- When JUPYTER_CONFIG_DIR, JUPYTER_DATA_DIR, or JUPYTER_RUNTIME_DIR is set, the corresponding resolver returns that explicit directory.
- Without overrides, the path resolvers return deterministic Linux, macOS, and Windows user and system defaults for the selected platform.
- When JUPYTER_NO_CONFIG is enabled, normal user and environment config paths are suppressed according to isolated-config behavior.
- When JUPYTER_PREFER_ENV_PATH changes preference, environment-level paths move before or after user paths without dropping either group.
- The package exposes the required task API paths `featurelifted.jupyter_config_dir`, `featurelifted.jupyter_config_path`, `featurelifted.jupyter_data_dir`, `featurelifted.jupyter_path`, `featurelifted.jupyter_runtime_dir` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jupyter_core, platformdirs`.
- Forbidden path access: `repo/, jupyter_core/paths.py`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement filesystem ownership probing.
- Do not implement platformdirs integration.
- Do not implement Jupyter CLI, migration, application, and troubleshoot modules.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When JUPYTER_CONFIG_PATH or JUPYTER_PATH is set, its entries are ordered ahead of the applicable default search paths.
- **B002** — When JUPYTER_CONFIG_DIR, JUPYTER_DATA_DIR, or JUPYTER_RUNTIME_DIR is set, the corresponding resolver returns that explicit directory.
- **B003** — Without overrides, the path resolvers return deterministic Linux, macOS, and Windows user and system defaults for the selected platform.
- **B004** — When JUPYTER_NO_CONFIG is enabled, normal user and environment config paths are suppressed according to isolated-config behavior.
- **B005** — When JUPYTER_PREFER_ENV_PATH changes preference, environment-level paths move before or after user paths without dropping either group.
- **B006** — The package exposes the required task API paths `featurelifted.jupyter_config_dir`, `featurelifted.jupyter_config_path`, `featurelifted.jupyter_data_dir`, `featurelifted.jupyter_path`, `featurelifted.jupyter_runtime_dir` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: jupyter_core, platformdirs.
<!-- featureliftbench:behavior-clauses:end -->
