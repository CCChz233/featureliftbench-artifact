# FeatureLift Task: PEP 517 build-system table validation

Extract a task-scoped subset of `build` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    BuildException,
    BuildSystemTableValidationError,
    parse_build_system_table,
    validate_source_directory,
)
```

## Required API Details

- `validate_source_directory(source_dir: 'str') -> 'None'`
- `parse_build_system_table(pyproject: 'dict[str, Any]') -> 'dict[str, Any]'`
- `BuildException` must be importable and raisable
- `BuildSystemTableValidationError` must be importable and raisable

## Required Behavior

- When parse_build_system_table receives pyproject data, it validates build-system.requires and build-backend and raises BuildSystemTableValidationError for malformed tables.
- When validate_source_directory checks a source tree, it accepts valid project roots and raises BuildException for missing or invalid source directories.
- The package exposes the required task API paths `featurelifted.validate_source_directory`, `featurelifted.parse_build_system_table`, `featurelifted.BuildException`, `featurelifted.BuildSystemTableValidationError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `build`.
- Forbidden path access: `repo/, build/`.
- Do not implement network access.
- Do not implement isolated env creation.
- Do not implement wheel build execution.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When parse_build_system_table receives pyproject data, it validates build-system.requires and build-backend and raises BuildSystemTableValidationError for malformed tables.
- **B002** — When validate_source_directory checks a source tree, it accepts valid project roots and raises BuildException for missing or invalid source directories.
- **B003** — The package exposes the required task API paths `featurelifted.validate_source_directory`, `featurelifted.parse_build_system_table`, `featurelifted.BuildException`, `featurelifted.BuildSystemTableValidationError` with the kinds and callable signatures listed in this contract.
- **B004** — the submitted package does not import forbidden upstream packages: build.
<!-- featureliftbench:behavior-clauses:end -->
