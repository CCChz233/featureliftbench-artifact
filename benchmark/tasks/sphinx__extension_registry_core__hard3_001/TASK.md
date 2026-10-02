# FeatureLift Task: Directive/role registry and extension setup loader

Extract a task-scoped subset of `sphinx` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ComponentRegistry,
    ExtensionError,
    ExtensionMetadata,
)
```

## Required API Details

- `ComponentRegistry() -> 'None'` class constructor
  - `ComponentRegistry.add_directive(self, name: 'str', directive: 'Any', override: 'bool' = False) -> 'None'`
  - `ComponentRegistry.directives` attribute must exist on instances
  - `ComponentRegistry.load_extension(self, name: 'str', setup: "Callable[['ComponentRegistry'], ExtensionMetadata]") -> 'ExtensionMetadata'`
- `ExtensionMetadata(version: 'str' = '1.0', parallel_read_safe: 'bool' = True, parallel_write_safe: 'bool' = True) -> None` class constructor
- `ExtensionError` must be importable and raisable

## Required Behavior

- `add_directive` and `add_role` register components; duplicates raise `ExtensionError` unless `override=True`.
- `load_extension` invokes a setup callable, records the extension, and returns `ExtensionMetadata`.
- Setup failures are wrapped in `ExtensionError`.
- The package exposes the required task API paths `featurelifted.ComponentRegistry`, `featurelifted.ComponentRegistry.add_directive`, `featurelifted.ComponentRegistry.directives`, `featurelifted.ComponentRegistry.load_extension`, `featurelifted.ExtensionMetadata`, `featurelifted.ExtensionError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sphinx`.
- Forbidden path access: `repo/, sphinx/`.
- Do not implement network access.
- Do not implement builder pipeline.
- Do not implement full application startup.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `add_directive` and `add_role` register components; duplicates raise `ExtensionError` unless `override=True`.
- **B002** — `load_extension` invokes a setup callable, records the extension, and returns `ExtensionMetadata`.
- **B003** — Setup failures are wrapped in `ExtensionError`.
- **B004** — The package exposes the required task API paths `featurelifted.ComponentRegistry`, `featurelifted.ComponentRegistry.add_directive`, `featurelifted.ComponentRegistry.directives`, `featurelifted.ComponentRegistry.load_extension`, `featurelifted.ExtensionMetadata`, `featurelifted.ExtensionError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: sphinx.
<!-- featureliftbench:behavior-clauses:end -->
