# FeatureLift Task: User/cache/config/data path resolver

Extract a task-scoped subset of `platformdirs` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    user_cache_dir,
    user_config_dir,
    user_data_dir,
)
```

## Required API Details

- `user_cache_dir(appname: 'str | None' = None, appauthor: 'str | bool | None' = None, version: 'str | None' = None, opinion: 'bool' = True, platform: 'str' = 'linux', env: 'Env' = None, home: 'str | None' = None) -> 'str'`
- `user_config_dir(appname: 'str | None' = None, appauthor: 'str | bool | None' = None, version: 'str | None' = None, roaming: 'bool' = False, platform: 'str' = 'linux', env: 'Env' = None, home: 'str | None' = None) -> 'str'`
- `user_data_dir(appname: 'str | None' = None, appauthor: 'str | bool | None' = None, version: 'str | None' = None, roaming: 'bool' = False, platform: 'str' = 'linux', env: 'Env' = None, home: 'str | None' = None) -> 'str'`

## Required Behavior

- `XDG_DATA_HOME`, `XDG_CONFIG_HOME`, and `XDG_CACHE_HOME` override defaults when they are non-blank.
- Defaults are `~/.local/share`, `~/.config`, and `~/.cache`.
- On macOS, data and config paths default to Library/Application Support and cache paths default to Library/Caches under home.
- On macOS, non-blank XDG directory overrides take precedence over the Library defaults.
- Data/config use `LOCALAPPDATA` by default and `APPDATA` when `roaming=True`.
- On Windows, appauthor, appauthor=False, version, roaming, and cache opinion options determine the exact appended path segments.
- The package exposes the required task API paths `featurelifted.user_cache_dir`, `featurelifted.user_config_dir`, `featurelifted.user_data_dir` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `platformdirs`.
- Forbidden path access: `repo/, src/platformdirs/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement Android path resolution.
- Do not implement site directories.
- Do not implement media directory helpers.
- Do not implement filesystem creation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `XDG_DATA_HOME`, `XDG_CONFIG_HOME`, and `XDG_CACHE_HOME` override defaults when they are non-blank.
- **B002** — Defaults are `~/.local/share`, `~/.config`, and `~/.cache`.
- **B003** — On macOS, data and config paths default to Library/Application Support and cache paths default to Library/Caches under home.
- **B004** — On macOS, non-blank XDG directory overrides take precedence over the Library defaults.
- **B005** — Data/config use `LOCALAPPDATA` by default and `APPDATA` when `roaming=True`.
- **B006** — On Windows, appauthor, appauthor=False, version, roaming, and cache opinion options determine the exact appended path segments.
- **B007** — The package exposes the required task API paths `featurelifted.user_cache_dir`, `featurelifted.user_config_dir`, `featurelifted.user_data_dir` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: platformdirs.
<!-- featureliftbench:behavior-clauses:end -->
