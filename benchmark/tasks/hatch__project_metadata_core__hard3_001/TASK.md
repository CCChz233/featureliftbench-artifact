# FeatureLift Task: normalize_project_metadata select_environment

Extract a task-scoped subset of `hatch` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    MetadataValidationError,
    normalize_project_metadata,
    select_environment,
)
```

## Required API Details

- `normalize_project_metadata(project: 'dict') -> 'dict'`
- `select_environment(envs: 'dict', name: 'str') -> 'dict'`
- `MetadataValidationError` must be importable and raisable

## Required Behavior

- `normalize_project_metadata` lowercases names, sorts dependencies, and validates classifiers.
- `select_environment` resolves environment inheritance and include chains.
- Circular inheritance raises `ValueError`; invalid classifiers raise `MetadataValidationError`.
- The package exposes the required task API paths `featurelifted.normalize_project_metadata`, `featurelifted.select_environment`, `featurelifted.MetadataValidationError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `hatch, hatchling`.
- Forbidden path access: `repo/, hatch/, hatchling/`.
- Do not implement network access.
- Do not implement build/env runner.
- Do not implement wheel generation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `normalize_project_metadata` lowercases names, sorts dependencies, and validates classifiers.
- **B002** — `select_environment` resolves environment inheritance and include chains.
- **B003** — Circular inheritance raises `ValueError`; invalid classifiers raise `MetadataValidationError`.
- **B004** — The package exposes the required task API paths `featurelifted.normalize_project_metadata`, `featurelifted.select_environment`, `featurelifted.MetadataValidationError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: hatch, hatchling.
<!-- featureliftbench:behavior-clauses:end -->
