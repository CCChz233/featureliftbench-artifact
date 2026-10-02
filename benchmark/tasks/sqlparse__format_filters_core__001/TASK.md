# FeatureLift Task: SQL format and filters core

Extract a task-scoped subset of `sqlparse` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    format,
)
```

## Required API Details

- `format(sql: str, encoding: str | None = None, **options: Any) -> str`
- `exceptions` module must be importable
  - `exceptions.SQLParseError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: format common SQL with keyword case, identifier case, comment stripping, reindentation, indentation width, and operator spacing. Required observable cases include format supports common options; formatter comment stripping and spacing.
- The extracted feature must support this observable behavior: preserve original formatter behavior for comments, whitespace, string literals, aliases, and nested expressions. Required observable cases include formatter rejects invalid options.
- The extracted feature must support this observable behavior: validate formatter options and reject invalid values. Required observable cases include formatter rejects invalid options.
- The package exposes the required task API paths `featurelifted.format`, `featurelifted.exceptions`, `featurelifted.exceptions.SQLParseError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sqlparse`.
- Do not implement SQL parsing into navigable token trees.
- Do not implement multi-statement script splitting.
- Do not implement command line interface.
- Do not implement original project tests.
- Do not implement documentation and release tooling.
- Do not implement packaging metadata from the original project.
- Do not implement dialect-perfect SQL validation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: format common SQL with keyword case, identifier case, comment stripping, reindentation, indentation width, and operator spacing. Required observable cases include format supports common options; formatter comment stripping and spacing.
- **B002** — The extracted feature must support this observable behavior: preserve original formatter behavior for comments, whitespace, string literals, aliases, and nested expressions. Required observable cases include formatter rejects invalid options.
- **B003** — The extracted feature must support this observable behavior: validate formatter options and reject invalid values. Required observable cases include formatter rejects invalid options.
- **B004** — The package exposes the required task API paths `featurelifted.format`, `featurelifted.exceptions`, `featurelifted.exceptions.SQLParseError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: sqlparse.
<!-- featureliftbench:behavior-clauses:end -->
