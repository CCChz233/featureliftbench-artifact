# FeatureLift Task: Combine path remap

Extract a task-scoped subset of `coverage` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    PathAliases,
)
```

## Required API Details

- `PathAliases(debugfn: 'Callable[[str], None] | None' = None, relative: 'bool' = False) -> 'None'` class constructor
  - `PathAliases.map(self, path: 'str', exists: 'Callable[[str], bool]' = <function source_exists>) -> 'str'`
  - `PathAliases.add(self, pattern: 'str', result: 'str') -> 'None'`
- `exceptions` module must be importable
  - `exceptions.ConfigError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: register glob-style path prefix aliases. Required observable cases include path aliases maps wildcard prefix; path aliases leaves unmatched paths; path aliases multiple rules; path aliases rejects trailing wildcards; path aliases skips nonexistent targets; path aliases relative pattern.
- The extracted feature must support this observable behavior: map absolute and relative paths through the first matching alias. Required observable cases include path aliases maps wildcard prefix; path aliases leaves unmatched paths; path aliases multiple rules; path aliases relative pattern.
- The extracted feature must support this observable behavior: normalize path separators to the alias result style. Required observable cases include path aliases skips nonexistent targets.
- The extracted feature must support this observable behavior: reject alias patterns ending in wildcards with ConfigError (message: must not end with wildcards). Required observable cases include path aliases rejects trailing wildcards.
- The extracted feature must support this observable behavior: skip mappings when the mapped target path does not exist. Required observable cases include path aliases skips nonexistent targets.
- The package exposes the required task API paths `featurelifted.PathAliases`, `featurelifted.PathAliases.map`, `featurelifted.PathAliases.add`, `featurelifted.exceptions`, `featurelifted.exceptions.ConfigError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `coverage`.
- Do not implement glob include/omit matching for measurement.
- Do not implement run-section configuration parsing.
- Do not implement InOrOut source selection policy.
- Do not implement coverage data combine I/O and SQLite storage.
- Do not implement original project tests and CLI.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: register glob-style path prefix aliases. Required observable cases include path aliases maps wildcard prefix; path aliases leaves unmatched paths; path aliases multiple rules; path aliases rejects trailing wildcards; path aliases skips nonexistent targets; path aliases relative pattern.
- **B002** — The extracted feature must support this observable behavior: map absolute and relative paths through the first matching alias. Required observable cases include path aliases maps wildcard prefix; path aliases leaves unmatched paths; path aliases multiple rules; path aliases relative pattern.
- **B003** — The extracted feature must support this observable behavior: normalize path separators to the alias result style. Required observable cases include path aliases skips nonexistent targets.
- **B004** — The extracted feature must support this observable behavior: reject alias patterns ending in wildcards with ConfigError (message: must not end with wildcards). Required observable cases include path aliases rejects trailing wildcards.
- **B005** — The extracted feature must support this observable behavior: skip mappings when the mapped target path does not exist. Required observable cases include path aliases skips nonexistent targets.
- **B006** — The package exposes the required task API paths `featurelifted.PathAliases`, `featurelifted.PathAliases.map`, `featurelifted.PathAliases.add`, `featurelifted.exceptions`, `featurelifted.exceptions.ConfigError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: coverage.
<!-- featureliftbench:behavior-clauses:end -->
