# FeatureLift Task: pytest mark expression evaluator

Extract a task-scoped subset of `pytest` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Expression,
    expression,
    ParseError,
)
```

## Required API Details

- `Expression(code: 'types.CodeType') -> 'None'` class constructor
  - `Expression.compile(input: 'str') -> 'Expression'`
  - `Expression.evaluate(self, matcher: 'MatcherCall') -> 'bool'`
- `ParseError` must be importable and raisable
- `expression` module must be importable
  - `expression.Scanner(input: 'str') -> 'None'` class constructor
    - `expression.Scanner.current` attribute must exist on instances
  - `expression.TokenType(*values)` class constructor
    - `expression.TokenType.IDENT` attribute must exist on instances

## Required Behavior

- The extracted feature must support this observable behavior: parse and compile mark expressions with and/or/not. Required observable cases include kwargs matcher.
- The extracted feature must support this observable behavior: evaluate expressions against a matcher callback. Required observable cases include and or logic; kwargs matcher; expression module scanner.
- The extracted feature must support this observable behavior: support identifier kwargs syntax for parameterized markers. Required observable cases include kwargs matcher.
- The extracted feature must support this observable behavior: empty expression evaluates to False. Required observable cases include empty expression is false; and or logic; expression module scanner.
- The package exposes the required task API paths `featurelifted.Expression`, `featurelifted.Expression.compile`, `featurelifted.Expression.evaluate`, `featurelifted.ParseError`, `featurelifted.expression`, `featurelifted.expression.Scanner`, `featurelifted.expression.Scanner.current`, `featurelifted.expression.TokenType`, `featurelifted.expression.TokenType.IDENT` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pytest, _pytest`.
- Do not implement full pytest collection and test running.
- Do not implement keyword -k matching.
- Do not implement marker registration and strict markers.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse and compile mark expressions with and/or/not. Required observable cases include kwargs matcher.
- **B002** — The extracted feature must support this observable behavior: evaluate expressions against a matcher callback. Required observable cases include and or logic; kwargs matcher; expression module scanner.
- **B003** — The extracted feature must support this observable behavior: support identifier kwargs syntax for parameterized markers. Required observable cases include kwargs matcher.
- **B004** — The extracted feature must support this observable behavior: empty expression evaluates to False. Required observable cases include empty expression is false; and or logic; expression module scanner.
- **B005** — The package exposes the required task API paths `featurelifted.Expression`, `featurelifted.Expression.compile`, `featurelifted.Expression.evaluate`, `featurelifted.ParseError`, `featurelifted.expression`, `featurelifted.expression.Scanner`, `featurelifted.expression.Scanner.current`, `featurelifted.expression.TokenType`, `featurelifted.expression.TokenType.IDENT` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: pytest, _pytest.
<!-- featureliftbench:behavior-clauses:end -->
