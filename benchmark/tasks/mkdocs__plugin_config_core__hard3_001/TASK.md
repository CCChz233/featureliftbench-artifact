# FeatureLift Task: Plugin config loading and event dispatch plan

Extract a task-scoped subset of `mkdocs` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    PluginCollection,
    PluginConfig,
    validate_plugin_config,
)
```

## Required API Details

- `PluginConfig(name: 'str', enabled: 'bool' = True, options: 'dict[str, Any]' = <factory>, priority: 'int' = 0) -> None` class constructor
- `PluginCollection() -> 'None'` class constructor
  - `PluginCollection.load(self, specs: 'list[PluginConfig]', hook_registry: 'dict[str, Callable[..., Any]] | None' = None) -> 'None'`
  - `PluginCollection.names` attribute must exist on instances
  - `PluginCollection.run_event(self, event_name: 'str', **kwargs) -> 'list[Any]'`
- `validate_plugin_config(name: 'str', options: 'dict[str, Any]', schema: 'dict[str, type]') -> 'list[str]'`

## Required Behavior

- `validate_plugin_config` reports missing, mistyped, and unexpected options.
- `PluginCollection.load` skips disabled plugins and registers hooks.
- `run_event` invokes hooks in ascending priority order.
- The package exposes the required task API paths `featurelifted.PluginConfig`, `featurelifted.PluginCollection`, `featurelifted.PluginCollection.load`, `featurelifted.PluginCollection.names`, `featurelifted.PluginCollection.run_event`, `featurelifted.validate_plugin_config` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `mkdocs`.
- Forbidden path access: `repo/, mkdocs/`.
- Do not implement network access.
- Do not implement build/render pipeline.
- Do not implement site generation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `validate_plugin_config` reports missing, mistyped, and unexpected options.
- **B002** — `PluginCollection.load` skips disabled plugins and registers hooks.
- **B003** — `run_event` invokes hooks in ascending priority order.
- **B004** — The package exposes the required task API paths `featurelifted.PluginConfig`, `featurelifted.PluginCollection`, `featurelifted.PluginCollection.load`, `featurelifted.PluginCollection.names`, `featurelifted.PluginCollection.run_event`, `featurelifted.validate_plugin_config` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: mkdocs.
<!-- featureliftbench:behavior-clauses:end -->
