# FeatureLift Task: Plugin option registration and checker selection

Extract a task-scoped subset of `flake8` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    apply_select_ignore,
    classify_plugins,
    OptionManager,
    OptionSpec,
    PluginSpec,
)
```

## Required API Details

- `OptionManager() -> 'None'` class constructor
- `PluginSpec(name: 'str', codes: 'list[str]', checker_type: 'str', options: 'list[OptionSpec]' = <factory>) -> None` class constructor
- `classify_plugins(plugins: 'list[PluginSpec]') -> 'Plugins'`
- `apply_select_ignore(plugins: 'Plugins', select: 'set[str] | None', ignore: 'set[str] | None') -> 'Plugins'`
- `OptionSpec(dest: 'str', parse_from_config: 'bool' = False, default: 'Any' = None) -> None` class constructor

## Required Behavior

- Register per-plugin options in `OptionManager`.
- Classify plugins into tree, logical_line, and physical_line checker groups.
- `apply_select_ignore` enables plugins whose codes intersect `select` and not `ignore`; when `select` is empty, ignore disables matching plugins.
- The package exposes the required task API paths `featurelifted.OptionManager`, `featurelifted.PluginSpec`, `featurelifted.classify_plugins`, `featurelifted.apply_select_ignore`, `featurelifted.OptionSpec` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `flake8`.
- Forbidden path access: `repo/, flake8/`.
- Do not implement network access.
- Do not implement file linting.
- Do not implement CLI application.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — Register per-plugin options in `OptionManager`.
- **B002** — Classify plugins into tree, logical_line, and physical_line checker groups.
- **B003** — `apply_select_ignore` enables plugins whose codes intersect `select` and not `ignore`; when `select` is empty, ignore disables matching plugins.
- **B004** — The package exposes the required task API paths `featurelifted.OptionManager`, `featurelifted.PluginSpec`, `featurelifted.classify_plugins`, `featurelifted.apply_select_ignore`, `featurelifted.OptionSpec` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: flake8.
<!-- featureliftbench:behavior-clauses:end -->
