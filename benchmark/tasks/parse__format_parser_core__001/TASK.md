# FeatureLift Task: Format-string parser

Extract a task-scoped subset of `parse` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    compile,
    parse,
    Parser,
    Result,
)
```

## Required API Details

- `Parser(format, case_sensitive=False)` class constructor
- `Result(fixed: tuple, named: dict) -> None` class constructor
- `compile(format, case_sensitive=False)`
- `parse(format, string, case_sensitive=False)`

## Required Behavior

- The extracted feature must support this observable behavior: literal and escaped-brace matching. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- The extracted feature must support this observable behavior: named and positional capture fields. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- The extracted feature must support this observable behavior: integer, float, word, and default string conversions. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- The extracted feature must support this observable behavior: case-sensitive option and full-string matching. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- The package exposes the required task API paths `featurelifted.Parser`, `featurelifted.Result`, `featurelifted.compile`, `featurelifted.parse` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `parse`.
- Forbidden path access: `repo/, parse/`.
- Do not implement custom type registries.
- Do not implement datetime formats.
- Do not implement search and findall.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: literal and escaped-brace matching. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- **B002** — The extracted feature must support this observable behavior: named and positional capture fields. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- **B003** — The extracted feature must support this observable behavior: integer, float, word, and default string conversions. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- **B004** — The extracted feature must support this observable behavior: case-sensitive option and full-string matching. Required observable cases include named and typed fields; positional and escaped braces; full match and case policy; word and default boundaries.
- **B005** — The package exposes the required task API paths `featurelifted.Parser`, `featurelifted.Result`, `featurelifted.compile`, `featurelifted.parse` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: parse.
<!-- featureliftbench:behavior-clauses:end -->
