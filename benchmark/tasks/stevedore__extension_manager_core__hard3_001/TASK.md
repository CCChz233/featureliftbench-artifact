# FeatureLift Task: ExtensionManager entry point discovery and loading

Extract a task-scoped subset of `stevedore` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    EntryPointSpec,
    error_on_conflict,
    Extension,
    ExtensionManager,
    ignore_conflicts,
    MultipleMatches,
    NamedExtensionManager,
    NoMatches,
)
```

## Required API Details

- `EntryPointSpec(name: 'str', value: 'str', group: 'str', loader: 'Callable[[], Any] | None' = None) -> None` class constructor
- `ExtensionManager(namespace: 'str', entry_points: 'Iterable[Any] | None' = None, invoke_on_load: 'bool' = False, invoke_args: 'tuple[Any, ...] | None' = None, invoke_kwds: 'dict[str, Any] | None' = None, propagate_map_exceptions: 'bool' = False, on_load_failure_callback: "Callable[['ExtensionManager', Any, BaseException], None] | None" = None, *, conflict_resolver: 'Callable[[str, str, list[Extension]], Extension]' = <function ignore_conflicts>) -> 'None'` class constructor
  - `ExtensionManager.map(self, func: 'Callable[..., Any]', *args: 'Any', **kwds: 'Any') -> 'list[Any]'`
  - `ExtensionManager.names(self) -> 'list[str]'`
  - `ExtensionManager.namespace` attribute must exist on instances
  - `ExtensionManager.__getitem__(self, name: 'str') -> 'Extension'`
- `NamedExtensionManager(namespace: 'str', names: 'Iterable[str]', entry_points: 'Iterable[Any] | None' = None, invoke_on_load: 'bool' = False, invoke_args: 'tuple[Any, ...] | None' = None, invoke_kwds: 'dict[str, Any] | None' = None, name_order: 'bool' = False, propagate_map_exceptions: 'bool' = False, on_load_failure_callback: 'Callable[[ExtensionManager, Any, BaseException], None] | None' = None, on_missing_entrypoints_callback: 'Callable[[Iterable[str]], None] | None' = None, *, conflict_resolver: 'Callable[[str, str, list[Extension]], Extension]' = <function ignore_conflicts>) -> 'None'` class constructor
  - `NamedExtensionManager.names(self) -> 'list[str]'`
- `NoMatches` must be importable and raisable
- `MultipleMatches` must be importable and raisable
- `error_on_conflict(namespace: 'str', name: 'str', entrypoints)`
- `ignore_conflicts(namespace: 'str', name: 'str', entrypoints)`
- `Extension(name: 'str', entry_point: 'Any', plugin: 'Any', obj: 'Any') -> 'None'` class constructor
  - `Extension.obj` attribute must exist on instances

## Required Behavior

- EntryPointSpec supplies deterministic entry-point name, namespace, and loader behavior for extension discovery.
- Loaded extensions retain their name, entry point, plugin, and optional invoked object for lookup and iteration.
- ExtensionManager filters entry points by namespace, loads matching plugins, and omits unrelated entry points.
- With invoke_on_load enabled, ExtensionManager invokes the plugin with invoke_args and invoke_kwds and stores the resulting object.
- When plugin loading fails, on_load_failure_callback receives the manager, entry point, and exception and the failed extension is skipped.
- names, items, iteration, containment, and keyed lookup expose the manager's successfully loaded extensions.
- map and map_method invoke callbacks across loaded extensions and preserve or propagate results and configured exceptions.
- Duplicate names follow ignore_conflicts or raise MultipleMatches under error_on_conflict.
- NamedExtensionManager filters requested names, reports missing names through its callback, and can preserve requested order.
- The package exposes the required task API paths `featurelifted.EntryPointSpec`, `featurelifted.ExtensionManager`, `featurelifted.ExtensionManager.map`, `featurelifted.ExtensionManager.names`, `featurelifted.ExtensionManager.namespace`, `featurelifted.ExtensionManager.__getitem__`, `featurelifted.NamedExtensionManager`, `featurelifted.NamedExtensionManager.names`, `featurelifted.NoMatches`, `featurelifted.MultipleMatches`, `featurelifted.error_on_conflict`, `featurelifted.ignore_conflicts`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `stevedore`.
- Forbidden path access: `repo/, stevedore/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement driver manager.
- Do not implement dispatch manager.
- Do not implement hook manager.
- Do not implement Sphinx extension.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — EntryPointSpec supplies deterministic entry-point name, namespace, and loader behavior for extension discovery.
- **B002** — Loaded extensions retain their name, entry point, plugin, and optional invoked object for lookup and iteration.
- **B003** — ExtensionManager filters entry points by namespace, loads matching plugins, and omits unrelated entry points.
- **B004** — With invoke_on_load enabled, ExtensionManager invokes the plugin with invoke_args and invoke_kwds and stores the resulting object.
- **B005** — When plugin loading fails, on_load_failure_callback receives the manager, entry point, and exception and the failed extension is skipped.
- **B006** — names, items, iteration, containment, and keyed lookup expose the manager's successfully loaded extensions.
- **B007** — map and map_method invoke callbacks across loaded extensions and preserve or propagate results and configured exceptions.
- **B008** — Duplicate names follow ignore_conflicts or raise MultipleMatches under error_on_conflict.
- **B009** — NamedExtensionManager filters requested names, reports missing names through its callback, and can preserve requested order.
- **B010** — The package exposes the required task API paths `featurelifted.EntryPointSpec`, `featurelifted.ExtensionManager`, `featurelifted.ExtensionManager.map`, `featurelifted.ExtensionManager.names`, `featurelifted.ExtensionManager.namespace`, `featurelifted.ExtensionManager.__getitem__`, `featurelifted.NamedExtensionManager`, `featurelifted.NamedExtensionManager.names`, `featurelifted.NoMatches`, `featurelifted.MultipleMatches`, `featurelifted.error_on_conflict`, `featurelifted.ignore_conflicts`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B011** — the submitted package does not import forbidden upstream packages: stevedore.
<!-- featureliftbench:behavior-clauses:end -->
