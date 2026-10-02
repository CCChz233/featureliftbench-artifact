# FeatureLift Task: SQL token tree navigation core

Extract a task-scoped subset of `sqlparse` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    parse,
    parsestream,
    sql,
    tokens,
)
```

## Required API Details

- `parse(sql: str, encoding: str | None = None) -> tuple[Statement, ...]`
- `parsestream(stream: Union[str, IO[str]], encoding: str | None = None) -> collections.abc.Generator[Statement, None, None]`
- `sql` module must be importable
  - `sql.Comparison(tokens=None)` class constructor
  - `sql.Identifier(tokens=None)` class constructor
  - `sql.Statement(tokens=None)` class constructor
  - `sql.Where(tokens=None)` class constructor
- `tokens` module must be importable
  - `tokens.Keyword` attribute must exist
- `tokens.Keyword.DML` attribute must exist

## Required Behavior

- The extracted feature must support this observable behavior: parse SQL text into Statement token trees. Required observable cases include parse returns statement tokens; token tree basics; token navigation and ancestor relationships.
- The extracted feature must support this observable behavior: support token tree traversal and identifier helpers. Required observable cases include token tree basics; cte aliases and identifier helpers.
- The extracted feature must support this observable behavior: preserve parent/ancestor relationships and comparison navigation. Required observable cases include token navigation and ancestor relationships.
- The extracted feature must support this observable behavior: extract identifiers, aliases, and CTE structure from parsed statements. Required observable cases include cte aliases and identifier helpers.
- The extracted feature must support this observable behavior: Identifier.get_name/get_real_name/get_alias and token ancestor navigation within Where clauses. Required observable cases include token navigation and ancestor relationships.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.parsestream`, `featurelifted.sql`, `featurelifted.sql.Comparison`, `featurelifted.sql.Identifier`, `featurelifted.sql.Statement`, `featurelifted.sql.Where`, `featurelifted.tokens`, `featurelifted.tokens.Keyword`, `featurelifted.tokens.Keyword.DML` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sqlparse`.
- Do not implement multi-statement script splitting.
- Do not implement SQL formatting and formatter filters.
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

- **B001** — The extracted feature must support this observable behavior: parse SQL text into Statement token trees. Required observable cases include parse returns statement tokens; token tree basics; token navigation and ancestor relationships.
- **B002** — The extracted feature must support this observable behavior: support token tree traversal and identifier helpers. Required observable cases include token tree basics; cte aliases and identifier helpers.
- **B003** — The extracted feature must support this observable behavior: preserve parent/ancestor relationships and comparison navigation. Required observable cases include token navigation and ancestor relationships.
- **B004** — The extracted feature must support this observable behavior: extract identifiers, aliases, and CTE structure from parsed statements. Required observable cases include cte aliases and identifier helpers.
- **B005** — The extracted feature must support this observable behavior: Identifier.get_name/get_real_name/get_alias and token ancestor navigation within Where clauses. Required observable cases include token navigation and ancestor relationships.
- **B006** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.parsestream`, `featurelifted.sql`, `featurelifted.sql.Comparison`, `featurelifted.sql.Identifier`, `featurelifted.sql.Statement`, `featurelifted.sql.Where`, `featurelifted.tokens`, `featurelifted.tokens.Keyword`, `featurelifted.tokens.Keyword.DML` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: sqlparse.
<!-- featureliftbench:behavior-clauses:end -->
