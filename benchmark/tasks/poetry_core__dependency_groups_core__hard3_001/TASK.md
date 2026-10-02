# FeatureLift Task: PEP 621 metadata and dependency group resolver

Extract a task-scoped subset of `poetry` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    DependencyGroup,
    DependencySpec,
    parse_project_dependencies,
    resolve_group,
)
```

## Required API Details

- `parse_project_dependencies(project: 'dict') -> 'dict[str, DependencyGroup]'`
- `resolve_group(name: 'str', groups: 'dict[str, DependencyGroup]', seen: 'set[str] | None' = None) -> 'list[DependencySpec]'`
- `DependencyGroup(name: 'str', optional: 'bool' = False, dependencies: 'list[DependencySpec]' = <factory>, includes: 'list[str]' = <factory>) -> None` class constructor
- `DependencySpec(name: 'str', constraint: 'str' = '*', optional: 'bool' = False, group: 'str | None' = None, marker: 'str | None' = None) -> None` class constructor

## Required Behavior

- `parse_project_dependencies` builds `DependencyGroup` objects from PEP 621 project metadata.
- resolve_group resolves a group's dependencies including transitive include-group references. parse_project_dependencies reads dependency-groups as mappings whose dependencies field is a list of requirement strings and whose include-group field is a list of group names.
- Circular includes raise `ValueError`.
- The package exposes the required task API paths `featurelifted.parse_project_dependencies`, `featurelifted.resolve_group`, `featurelifted.DependencyGroup`, `featurelifted.DependencySpec` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `poetry, poetry_core`.
- Forbidden path access: `repo/, poetry/, poetry_core/`.
- Do not implement network access.
- Do not implement package build.
- Do not implement wheel/sdist generation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `parse_project_dependencies` builds `DependencyGroup` objects from PEP 621 project metadata.
- **B002** — resolve_group resolves a group's dependencies including transitive include-group references. parse_project_dependencies reads dependency-groups as mappings whose dependencies field is a list of requirement strings and whose include-group field is a list of group names.
- **B003** — Circular includes raise `ValueError`.
- **B004** — The package exposes the required task API paths `featurelifted.parse_project_dependencies`, `featurelifted.resolve_group`, `featurelifted.DependencyGroup`, `featurelifted.DependencySpec` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: poetry, poetry_core.
<!-- featureliftbench:behavior-clauses:end -->
