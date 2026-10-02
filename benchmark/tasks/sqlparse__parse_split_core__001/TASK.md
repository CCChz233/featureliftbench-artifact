# FeatureLift Task: SQL parse and split core

Extract a task-scoped subset of `sqlparse` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
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
- `sql` module must be importable
  - `sql.Statement(tokens=None)` class constructor
- `tokens` module must be importable
  - `tokens.Keyword` attribute must exist
- `tokens.Keyword.DML` attribute must exist

## Required Behavior

- The extracted feature must support this observable behavior: parse SQL text into Statement token trees. Required observable cases include parse returns statement tokens; parse multiple statements.
- The extracted feature must support this observable behavior: split multi-statement SQL scripts while respecting strings, comments, and nesting. Required observable cases include split respects quoted semicolons; split handles comments and embedded semicolons.
- The extracted feature must support this observable behavior: preserve statement-splitting behavior for semicolons inside quotes and comments. Required observable cases include split handles comments and embedded semicolons.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.parsestream`, `featurelifted.split`, `featurelifted.sql`, `featurelifted.sql.Statement`, `featurelifted.tokens`, `featurelifted.tokens.Keyword`, `featurelifted.tokens.Keyword.DML` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `sqlparse`.
- Do not implement SQL formatting and formatter filters.
- Do not implement token tree navigation helpers beyond basic parse output.
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

- **B001** — The extracted feature must support this observable behavior: parse SQL text into Statement token trees. Required observable cases include parse returns statement tokens; parse multiple statements.
- **B002** — The extracted feature must support this observable behavior: split multi-statement SQL scripts while respecting strings, comments, and nesting. Required observable cases include split respects quoted semicolons; split handles comments and embedded semicolons.
- **B003** — The extracted feature must support this observable behavior: preserve statement-splitting behavior for semicolons inside quotes and comments. Required observable cases include split handles comments and embedded semicolons.
- **B004** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.parsestream`, `featurelifted.split`, `featurelifted.sql`, `featurelifted.sql.Statement`, `featurelifted.tokens`, `featurelifted.tokens.Keyword`, `featurelifted.tokens.Keyword.DML` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: sqlparse.
<!-- featureliftbench:behavior-clauses:end -->
