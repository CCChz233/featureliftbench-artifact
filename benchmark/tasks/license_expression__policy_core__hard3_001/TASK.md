# FeatureLift Task: License expression parse and policy evaluation

Extract a task-scoped subset of `license_expression` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ExpressionInfo,
    ExpressionParseError,
    LicenseSymbol,
    Licensing,
)
```

## Required API Details

- `LicenseSymbol(key: 'str', aliases: 'tuple[str, ...] | list[str]' = (), is_exception: 'bool' = False) -> 'None'` class constructor
  - `LicenseSymbol.key` attribute must exist on instances
- `Licensing(symbols: 'tuple[LicenseSymbol | str, ...] | list[LicenseSymbol | str]' = ()) -> 'None'` class constructor
  - `Licensing.parse(self, expression: 'str', validate: 'bool' = False, strict: 'bool' = False) -> 'Node'`
  - `Licensing.validate(self, expression: 'str') -> 'ExpressionInfo'`
  - `Licensing.license_symbols(self, expression: 'str | Node') -> 'list[LicenseSymbol]'`
  - `Licensing.evaluate_policy(self, expression: 'str', allowed: 'tuple[str, ...] | list[str] | set[str]' = (), denied: 'tuple[str, ...] | list[str] | set[str]' = ()) -> 'dict[str, Any]'`
- `ExpressionInfo(original_expression: 'str', normalized_expression: 'str | None' = None, errors: 'list[str] | None' = None, invalid_symbols: 'list[str] | None' = None) -> None` class constructor
- `ExpressionParseError` must be importable and raisable

## Required Behavior

- Parse symbols, `AND`, `OR`, `WITH`, and parentheses.
- `AND` binds tighter than `OR`.
- Parentheses override precedence.
- `WITH` binds a license symbol to an exception symbol.
- Aliases normalize to canonical `LicenseSymbol.key` values.
- When parse(..., strict=True) is used, exception symbols cannot appear as plain licenses and raise ExpressionParseError; default parse(..., strict=False) does not enforce that check.
- When parse(..., strict=True) is used, plain license symbols cannot be used as WITH exceptions and raise ExpressionParseError; default parse(..., strict=False) does not raise for that misuse.
- `validate()` returns `ExpressionInfo` with errors and invalid symbols instead of raising for unknown symbols.
- `evaluate_policy()` returns a dictionary with `status`, `normalized`, `symbols`, `denied`, `unknown`, and `errors`.
- The package exposes the required task API paths `featurelifted.LicenseSymbol`, `featurelifted.LicenseSymbol.key`, `featurelifted.Licensing`, `featurelifted.Licensing.parse`, `featurelifted.Licensing.validate`, `featurelifted.Licensing.license_symbols`, `featurelifted.Licensing.evaluate_policy`, `featurelifted.ExpressionInfo`, `featurelifted.ExpressionParseError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `license_expression, boolean`.
- Forbidden path access: `repo/, src/license_expression/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement ScanCode license database.
- Do not implement SPDX bundled datasets.
- Do not implement boolean.py dependency.
- Do not implement HTML rendering templates.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — Parse symbols, `AND`, `OR`, `WITH`, and parentheses.
- **B002** — `AND` binds tighter than `OR`.
- **B003** — Parentheses override precedence.
- **B004** — `WITH` binds a license symbol to an exception symbol.
- **B005** — Aliases normalize to canonical `LicenseSymbol.key` values.
- **B006** — When parse(..., strict=True) is used, exception symbols cannot appear as plain licenses and raise ExpressionParseError; default parse(..., strict=False) does not enforce that check.
- **B007** — When parse(..., strict=True) is used, plain license symbols cannot be used as WITH exceptions and raise ExpressionParseError; default parse(..., strict=False) does not raise for that misuse.
- **B008** — `validate()` returns `ExpressionInfo` with errors and invalid symbols instead of raising for unknown symbols.
- **B009** — `evaluate_policy()` returns a dictionary with `status`, `normalized`, `symbols`, `denied`, `unknown`, and `errors`.
- **B010** — The package exposes the required task API paths `featurelifted.LicenseSymbol`, `featurelifted.LicenseSymbol.key`, `featurelifted.Licensing`, `featurelifted.Licensing.parse`, `featurelifted.Licensing.validate`, `featurelifted.Licensing.license_symbols`, `featurelifted.Licensing.evaluate_policy`, `featurelifted.ExpressionInfo`, `featurelifted.ExpressionParseError` with the kinds and callable signatures listed in this contract.
- **B011** — the submitted package does not import forbidden upstream packages: license_expression, boolean.
<!-- featureliftbench:behavior-clauses:end -->
