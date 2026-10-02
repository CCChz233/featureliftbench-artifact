# FeatureLift Task: parse_spec match_version

Extract a task-scoped subset of `virtualenv` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    discover_paths,
    InvalidInterpreterSpec,
    match_version,
    parse_spec,
)
```

## Required API Details

- `parse_spec(spec: 'str') -> 'tuple[str | None, tuple[str, ...]]'`
- `match_version(version: 'str', constraint: 'str | None') -> 'bool'`
- `discover_paths(candidates: 'list[str]', spec: 'str') -> 'list[str]'`
- `InvalidInterpreterSpec` must be importable and raisable

## Required Behavior

- `parse_spec` parses version constraints and path globs from interpreter specs.
- `match_version` evaluates constraint operators including `~=`.
- discover_paths filters candidate paths by spec, including reading an implementation-prefixed version such as python3.11 from the path string when the spec is python>=3.11.
- The package exposes the required task API paths `featurelifted.parse_spec`, `featurelifted.match_version`, `featurelifted.discover_paths`, `featurelifted.InvalidInterpreterSpec` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `virtualenv`.
- Forbidden path access: `repo/, virtualenv/`.
- Do not implement network access.
- Do not implement environment creation.
- Do not implement process spawning.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `parse_spec` parses version constraints and path globs from interpreter specs.
- **B002** — `match_version` evaluates constraint operators including `~=`.
- **B003** — discover_paths filters candidate paths by spec, including reading an implementation-prefixed version such as python3.11 from the path string when the spec is python>=3.11.
- **B004** — The package exposes the required task API paths `featurelifted.parse_spec`, `featurelifted.match_version`, `featurelifted.discover_paths`, `featurelifted.InvalidInterpreterSpec` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: virtualenv.
<!-- featureliftbench:behavior-clauses:end -->
