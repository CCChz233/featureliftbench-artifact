# FeatureLift Task: SQL parse, split, and format core

Extract a task-scoped subset of `sqlparse` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    format,
    parse,
    parsestream,
    split,
    sql,
    tokens,
)
```

## Required API Details

- `parse(sql: str, encoding: str | None = None) -> tuple[Statement, ...]`
- `parsestream(stream: Union[str, IO[str]], encoding: str | None = None) -> collections.abc.Generator[Statement, None, None]`
- `split(sql: str, encoding: str | None = None, strip_semicolon: bool = False) -> list[str]`
- `format(sql: str, encoding: str | None = None, **options: Any) -> str`
- `sql` module must be importable
  - `sql.Comparison(tokens=None)` class constructor
  - `sql.Identifier(tokens=None)` class constructor
  - `sql.Statement(tokens=None)` class constructor
  - `sql.Where(tokens=None)` class constructor
- `tokens` module must be importable
  - `tokens.Keyword` attribute must exist
- `exceptions` module must be importable
  - `exceptions.SQLParseError` must be importable and raisable
- `tokens.Keyword.DML` attribute must exist

## Required Behavior

- The extracted feature must support this observable behavior: parse SQL text into Statement token trees. Required observable cases include parse returns statement tokens; token navigation and ancestor relationships.
- The extracted feature must support this observable behavior: split multi-statement SQL scripts while respecting strings, comments, and nesting. Required observable cases include split respects quoted semicolons; split handles comments and embedded semicolons.
- The extracted feature must support this observable behavior: support common token tree traversal and identifier helpers. Required observable cases include format supports common options; cte aliases and identifier helpers.
- The extracted feature must support this observable behavior: format common SQL with keyword case, identifier case, comment stripping, reindentation, indentation width, and operator spacing. Required observable cases include format supports common options; formatter comment stripping and spacing; formatter rejects invalid options.
- The extracted feature must support this observable behavior: preserve original behavior for comments, whitespace, string literals, aliases, functions, nested expressions, CTEs, CASE expressions, and common DDL/DML. Required observable cases include cte aliases and identifier helpers.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.parsestream`, `featurelifted.split`, `featurelifted.format`, `featurelifted.sql`, `featurelifted.sql.Comparison`, `featurelifted.sql.Identifier`, `featurelifted.sql.Statement`, `featurelifted.sql.Where`, `featurelifted.tokens`, `featurelifted.tokens.Keyword`, `featurelifted.exceptions`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sqlparse`.
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

- **B001** — The extracted feature must support this observable behavior: parse SQL text into Statement token trees. Required observable cases include parse returns statement tokens; token navigation and ancestor relationships.
- **B002** — The extracted feature must support this observable behavior: split multi-statement SQL scripts while respecting strings, comments, and nesting. Required observable cases include split respects quoted semicolons; split handles comments and embedded semicolons.
- **B003** — The extracted feature must support this observable behavior: support common token tree traversal and identifier helpers. Required observable cases include format supports common options; cte aliases and identifier helpers.
- **B004** — The extracted feature must support this observable behavior: format common SQL with keyword case, identifier case, comment stripping, reindentation, indentation width, and operator spacing. Required observable cases include format supports common options; formatter comment stripping and spacing; formatter rejects invalid options.
- **B005** — The extracted feature must support this observable behavior: preserve original behavior for comments, whitespace, string literals, aliases, functions, nested expressions, CTEs, CASE expressions, and common DDL/DML. Required observable cases include cte aliases and identifier helpers.
- **B006** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.parsestream`, `featurelifted.split`, `featurelifted.format`, `featurelifted.sql`, `featurelifted.sql.Comparison`, `featurelifted.sql.Identifier`, `featurelifted.sql.Statement`, `featurelifted.sql.Where`, `featurelifted.tokens`, `featurelifted.tokens.Keyword`, `featurelifted.exceptions`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: sqlparse.
<!-- featureliftbench:behavior-clauses:end -->
