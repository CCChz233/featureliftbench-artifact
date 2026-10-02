# FeatureLift Task: Hook specification, registration, and call ordering

Extract a task-scoped subset of `pluggy` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    HookimplMarker,
    HookspecMarker,
    PluginManager,
    PluginValidationError,
)
```

## Required API Details

- `PluginManager(project_name)` class constructor
  - `PluginManager.add_hookspecs(self, module_or_class)`
  - `PluginManager.get_name(self, plugin)`
  - `PluginManager.has_plugin(self, name)`
  - `PluginManager.hook` attribute must exist on instances
  - `PluginManager.register(self, plugin, name=None)`
  - `PluginManager.unregister(self, plugin=None, name=None)`
- `HookspecMarker(project_name)` class constructor
- `HookimplMarker(project_name)` class constructor
- `PluginValidationError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: declare hook specifications with HookspecMarker. Required observable cases include basic hook registration and ordering; validation unregister and plugin names.
- The extracted feature must support this observable behavior: register plugins and call hook implementations through PluginManager. Required observable cases include basic hook registration and ordering; hook historic and subset hooknames.
- The extracted feature must support this observable behavior: respect tryfirst and trylast ordering. Required observable cases include basic hook registration and ordering; validation unregister and plugin names.
- The extracted feature must support this observable behavior: support firstresult hooks. Required observable cases include validation unregister and plugin names.
- The extracted feature must support this observable behavior: support hookwrapper implementations that inspect or modify results. Required observable cases include firstresult and hookwrapper result mutation.
- The extracted feature must support this observable behavior: reject unknown hook implementation arguments during validation. Required observable cases include validation unregister and plugin names.
- The extracted feature must support this observable behavior: support unregistering plugins and querying registered plugin names. Required observable cases include validation unregister and plugin names.
- The package exposes the required task API paths `featurelifted.PluginManager`, `featurelifted.PluginManager.add_hookspecs`, `featurelifted.PluginManager.get_name`, `featurelifted.PluginManager.has_plugin`, `featurelifted.PluginManager.hook`, `featurelifted.PluginManager.register`, `featurelifted.PluginManager.unregister`, `featurelifted.HookspecMarker`, `featurelifted.HookimplMarker`, `featurelifted.PluginValidationError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pluggy`.
- Do not implement pytest integration.
- Do not implement project packaging metadata.
- Do not implement development tests and release tooling.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: declare hook specifications with HookspecMarker. Required observable cases include basic hook registration and ordering; validation unregister and plugin names.
- **B002** — The extracted feature must support this observable behavior: register plugins and call hook implementations through PluginManager. Required observable cases include basic hook registration and ordering; hook historic and subset hooknames.
- **B003** — The extracted feature must support this observable behavior: respect tryfirst and trylast ordering. Required observable cases include basic hook registration and ordering; validation unregister and plugin names.
- **B004** — The extracted feature must support this observable behavior: support firstresult hooks. Required observable cases include validation unregister and plugin names.
- **B005** — The extracted feature must support this observable behavior: support hookwrapper implementations that inspect or modify results. Required observable cases include firstresult and hookwrapper result mutation.
- **B006** — The extracted feature must support this observable behavior: reject unknown hook implementation arguments during validation. Required observable cases include validation unregister and plugin names.
- **B007** — The extracted feature must support this observable behavior: support unregistering plugins and querying registered plugin names. Required observable cases include validation unregister and plugin names.
- **B008** — The package exposes the required task API paths `featurelifted.PluginManager`, `featurelifted.PluginManager.add_hookspecs`, `featurelifted.PluginManager.get_name`, `featurelifted.PluginManager.has_plugin`, `featurelifted.PluginManager.hook`, `featurelifted.PluginManager.register`, `featurelifted.PluginManager.unregister`, `featurelifted.HookspecMarker`, `featurelifted.HookimplMarker`, `featurelifted.PluginValidationError` with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: pluggy.
<!-- featureliftbench:behavior-clauses:end -->
