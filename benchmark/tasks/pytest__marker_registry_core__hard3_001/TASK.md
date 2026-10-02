# FeatureLift Task: MarkerRegistry

Extract a task-scoped subset of `pytest` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Marker,
    MarkerRegistry,
    UnknownMarkerWarning,
)
```

## Required API Details

- `MarkerRegistry() -> 'None'` class constructor
  - `MarkerRegistry.from_ini(value: 'str | list[str]') -> "'MarkerRegistry'"`
  - `MarkerRegistry.check_unknown(self, name: 'str', *, strict: 'bool' = False) -> 'None'`
  - `MarkerRegistry.get(self, name: 'str') -> 'Marker | None'`
  - `MarkerRegistry.merge_plugin_markers(self, plugin_markers: 'dict[str, str]') -> 'None'`
  - `MarkerRegistry.register(self, name: 'str', description: 'str' = '', *, _overwrite: 'bool' = False) -> 'None'`
- `Marker(name: 'str', description: 'str' = '', *, args: 'tuple' = (), kwargs: 'dict | None' = None) -> 'None'` class constructor
- `UnknownMarkerWarning` must be importable and raisable

## Required Behavior

- `MarkerRegistry.from_ini` parses marker lines from ini configuration.
- `merge_plugin_markers` adds plugin-provided markers without overwriting existing ones.
- `check_unknown` warns or raises for unregistered markers.
- The package exposes the required task API paths `featurelifted.MarkerRegistry`, `featurelifted.MarkerRegistry.from_ini`, `featurelifted.MarkerRegistry.check_unknown`, `featurelifted.MarkerRegistry.get`, `featurelifted.MarkerRegistry.merge_plugin_markers`, `featurelifted.MarkerRegistry.register`, `featurelifted.Marker`, `featurelifted.UnknownMarkerWarning` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pytest, _pytest`.
- Forbidden path access: `repo/, pytest/, _pytest/`.
- Do not implement network access.
- Do not implement test collection.
- Do not implement plugin loading.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `MarkerRegistry.from_ini` parses marker lines from ini configuration.
- **B002** — `merge_plugin_markers` adds plugin-provided markers without overwriting existing ones.
- **B003** — `check_unknown` warns or raises for unregistered markers.
- **B004** — The package exposes the required task API paths `featurelifted.MarkerRegistry`, `featurelifted.MarkerRegistry.from_ini`, `featurelifted.MarkerRegistry.check_unknown`, `featurelifted.MarkerRegistry.get`, `featurelifted.MarkerRegistry.merge_plugin_markers`, `featurelifted.MarkerRegistry.register`, `featurelifted.Marker`, `featurelifted.UnknownMarkerWarning` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: pytest, _pytest.
<!-- featureliftbench:behavior-clauses:end -->
