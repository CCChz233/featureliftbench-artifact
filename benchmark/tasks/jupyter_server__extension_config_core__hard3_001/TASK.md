# FeatureLift Task: Server extension discovery and enable/disable config merge

Extract a task-scoped subset of `jupyter_server` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ExtensionConfigStore,
    filter_enabled_extensions,
    merge_extension_configs,
    recursive_update,
)
```

## Required API Details

- `ExtensionConfigStore(config_dir: 'str | Path') -> 'None'` class constructor
  - `ExtensionConfigStore.disable(self, name: 'str') -> 'None'`
  - `ExtensionConfigStore.enabled(self, name: 'str') -> 'bool'`
  - `ExtensionConfigStore.get_extensions(self) -> 'dict[str, bool]'`
- `merge_extension_configs(config_paths: 'list[str | Path]') -> 'dict[str, bool]'`
- `filter_enabled_extensions(entry_points: 'list[str]', extensions: 'dict[str, bool]') -> 'list[str]'`
- `recursive_update(target: 'dict[str, Any]', new: 'dict[str, Any]') -> 'None'`

## Required Behavior

- When extension config fragments are merged, recursive_update combines nested mappings while later fragments override earlier scalar values.
- When ExtensionConfigStore is constructed with a config directory, it auto-loads jupyter_server_config.json plus JSON fragments under jupyter_server_config.d/, later .d fragments override earlier values for the same extension, and enable/disable writes and reloads the corresponding per-extension JSON state.
- When entry-point extensions are filtered, explicitly disabled names are omitted and enabled or unspecified names remain discoverable.
- The package exposes the required task API paths `featurelifted.ExtensionConfigStore`, `featurelifted.ExtensionConfigStore.disable`, `featurelifted.ExtensionConfigStore.enabled`, `featurelifted.ExtensionConfigStore.get_extensions`, `featurelifted.merge_extension_configs`, `featurelifted.filter_enabled_extensions`, `featurelifted.recursive_update` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jupyter_server`.
- Forbidden path access: `repo/, jupyter_server/`.
- Do not implement network access.
- Do not implement server process.
- Do not implement Tornado handlers.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When extension config fragments are merged, recursive_update combines nested mappings while later fragments override earlier scalar values.
- **B002** — When ExtensionConfigStore is constructed with a config directory, it auto-loads jupyter_server_config.json plus JSON fragments under jupyter_server_config.d/, later .d fragments override earlier values for the same extension, and enable/disable writes and reloads the corresponding per-extension JSON state.
- **B003** — When entry-point extensions are filtered, explicitly disabled names are omitted and enabled or unspecified names remain discoverable.
- **B004** — The package exposes the required task API paths `featurelifted.ExtensionConfigStore`, `featurelifted.ExtensionConfigStore.disable`, `featurelifted.ExtensionConfigStore.enabled`, `featurelifted.ExtensionConfigStore.get_extensions`, `featurelifted.merge_extension_configs`, `featurelifted.filter_enabled_extensions`, `featurelifted.recursive_update` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: jupyter_server.
<!-- featureliftbench:behavior-clauses:end -->
