# FeatureLift Task: Hook specification validation and discovery

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
  - `PluginManager.check_pending(self)`
  - `PluginManager.add_hookspecs(self, module_or_class)`
  - `PluginManager.hook` attribute must exist on instances
  - `PluginManager.register(self, plugin, name=None)`
- `HookspecMarker(project_name)` class constructor
- `HookimplMarker(project_name)` class constructor
- `PluginValidationError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: declare hook specifications with HookspecMarker including firstresult and historic flags. Required observable cases include hookwrapper must be generator.
- The extracted feature must support this observable behavior: reject hook implementations with unknown arguments during registration. Required observable cases include unknown hook argument rejected; hookwrapper must be generator.
- The extracted feature must support this observable behavior: reject hookwrapper implementations that are not generator functions. Required observable cases include hookwrapper must be generator.
- The extracted feature must support this observable behavior: reject historic hookwrapper combinations via PluginValidationError. Required observable cases include historic hookwrapper combination rejected.
- The extracted feature must support this observable behavior: check_pending raises for unknown non-optional hook implementations. Required observable cases include check pending requires optional for unknown hooks; hookwrapper must be generator.
- The extracted feature must support this observable behavior: support optionalhook implementations for undeclared hooks. Required observable cases include hookwrapper must be generator.
- The extracted feature must support this observable behavior: replay historic hook calls for plugins registered after the first dispatch. Required observable cases include historic hook replays for late registration.
- The package exposes the required task API paths `featurelifted.PluginManager`, `featurelifted.PluginManager.check_pending`, `featurelifted.PluginManager.add_hookspecs`, `featurelifted.PluginManager.hook`, `featurelifted.PluginManager.register`, `featurelifted.HookspecMarker`, `featurelifted.HookimplMarker`, `featurelifted.PluginValidationError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pluggy`.
- Do not implement pytest integration and setuptools entry point loading.
- Do not implement project packaging metadata.
- Do not implement development tests and release tooling.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: declare hook specifications with HookspecMarker including firstresult and historic flags. Required observable cases include hookwrapper must be generator.
- **B002** — The extracted feature must support this observable behavior: reject hook implementations with unknown arguments during registration. Required observable cases include unknown hook argument rejected; hookwrapper must be generator.
- **B003** — The extracted feature must support this observable behavior: reject hookwrapper implementations that are not generator functions. Required observable cases include hookwrapper must be generator.
- **B004** — The extracted feature must support this observable behavior: reject historic hookwrapper combinations via PluginValidationError. Required observable cases include historic hookwrapper combination rejected.
- **B005** — The extracted feature must support this observable behavior: check_pending raises for unknown non-optional hook implementations. Required observable cases include check pending requires optional for unknown hooks; hookwrapper must be generator.
- **B006** — The extracted feature must support this observable behavior: support optionalhook implementations for undeclared hooks. Required observable cases include hookwrapper must be generator.
- **B007** — The extracted feature must support this observable behavior: replay historic hook calls for plugins registered after the first dispatch. Required observable cases include historic hook replays for late registration.
- **B008** — The package exposes the required task API paths `featurelifted.PluginManager`, `featurelifted.PluginManager.check_pending`, `featurelifted.PluginManager.add_hookspecs`, `featurelifted.PluginManager.hook`, `featurelifted.PluginManager.register`, `featurelifted.HookspecMarker`, `featurelifted.HookimplMarker`, `featurelifted.PluginValidationError` with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: pluggy.
<!-- featureliftbench:behavior-clauses:end -->
