# FeatureLift Task: JSONPath parse, find, and update core

Extract a task-scoped subset of `jsonpath_ng` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    exceptions,
    parse,
)
```

## Required API Details

- `parse(path, debug=False)`
- `exceptions` module must be importable
  - `exceptions.JsonPathLexerError` must be importable and raisable
  - `exceptions.JsonPathParserError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse JSONPath strings into expression objects. Required observable cases include parse find simple path; root child fields; filter expression selects items; invalid expression raises.
- The extracted feature must support this observable behavior: find matching values in dict/list document trees. Required observable cases include parse find simple path; wildcard array find; root child fields; update nested path.
- The extracted feature must support this observable behavior: update values at matching paths in place. Required observable cases include update value in place; update nested path.
- The extracted feature must support this observable behavior: filter expressions with comparison operators. Required observable cases include filter expression selects items; invalid expression raises.
- The extracted feature must support this observable behavior: array slices and wildcard/index segments. Required observable cases include wildcard array find; bracket slice selects range; negative index selects last.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.exceptions`, `featurelifted.exceptions.JsonPathLexerError`, `featurelifted.exceptions.JsonPathParserError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `jsonpath_ng`.
- Do not implement CLI bin/jsonpath.py.
- Do not implement original jsonpath_ng import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse JSONPath strings into expression objects. Required observable cases include parse find simple path; root child fields; filter expression selects items; invalid expression raises.
- **B002** — The extracted feature must support this observable behavior: find matching values in dict/list document trees. Required observable cases include parse find simple path; wildcard array find; root child fields; update nested path.
- **B003** — The extracted feature must support this observable behavior: update values at matching paths in place. Required observable cases include update value in place; update nested path.
- **B004** — The extracted feature must support this observable behavior: filter expressions with comparison operators. Required observable cases include filter expression selects items; invalid expression raises.
- **B005** — The extracted feature must support this observable behavior: array slices and wildcard/index segments. Required observable cases include wildcard array find; bracket slice selects range; negative index selects last.
- **B006** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.exceptions`, `featurelifted.exceptions.JsonPathLexerError`, `featurelifted.exceptions.JsonPathParserError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: jsonpath_ng.
<!-- featureliftbench:behavior-clauses:end -->
