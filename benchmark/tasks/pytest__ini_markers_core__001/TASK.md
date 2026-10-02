# FeatureLift Task: pytest ini markers parsing

Extract a task-scoped subset of `pytest` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    MarkerRegistry,
    parse_linelist,
    split_marker_line,
)
```

## Required API Details

- `MarkerRegistry(lines: 'list[str]' = <factory>) -> None` class constructor
  - `MarkerRegistry.from_ini(value: 'str | list[str]') -> "'MarkerRegistry'"`
  - `MarkerRegistry.names(self) -> 'list[str]'`
  - `MarkerRegistry.add_line(self, line: 'str') -> 'None'`
  - `MarkerRegistry.description(self, name: 'str') -> 'str'`
  - `MarkerRegistry.from_lines(lines: 'list[str]') -> "'MarkerRegistry'"`
- `parse_linelist(value: 'str | list[str]') -> 'list[str]'`
- `split_marker_line(line: 'str') -> 'tuple[str, str]'`

## Required Behavior

- The extracted feature must support this observable behavior: parse multiline ini markers values into linelist entries. Required observable cases include parse multiline markers; split marker line whitespace.
- The extracted feature must support this observable behavior: append marker lines preserving order. Required observable cases include append marker line; registry module order preserved.
- The extracted feature must support this observable behavior: split marker lines into name and description (strip name; preserve description whitespace). Required observable cases include linelist strips blank lines; split marker line whitespace.
- The extracted feature must support this observable behavior: strip whitespace from linelist entries. Required observable cases include linelist strips blank lines.
- The extracted feature must support this observable behavior: MarkerRegistry preserves marker declaration order from ini lines. Required observable cases include append marker line; split marker line whitespace.
- The package exposes the required task API paths `featurelifted.MarkerRegistry`, `featurelifted.MarkerRegistry.from_ini`, `featurelifted.MarkerRegistry.names`, `featurelifted.MarkerRegistry.add_line`, `featurelifted.MarkerRegistry.description`, `featurelifted.MarkerRegistry.from_lines`, `featurelifted.parse_linelist`, `featurelifted.split_marker_line` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pytest, _pytest`.
- Do not implement full Config initialization and plugin loading.
- Do not implement strict marker validation at collection.
- Do not implement conftest and pyproject discovery.
- Do not implement CLI --markers display.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse multiline ini markers values into linelist entries. Required observable cases include parse multiline markers; split marker line whitespace.
- **B002** — The extracted feature must support this observable behavior: append marker lines preserving order. Required observable cases include append marker line; registry module order preserved.
- **B003** — The extracted feature must support this observable behavior: split marker lines into name and description (strip name; preserve description whitespace). Required observable cases include linelist strips blank lines; split marker line whitespace.
- **B004** — The extracted feature must support this observable behavior: strip whitespace from linelist entries. Required observable cases include linelist strips blank lines.
- **B005** — The extracted feature must support this observable behavior: MarkerRegistry preserves marker declaration order from ini lines. Required observable cases include append marker line; split marker line whitespace.
- **B006** — The package exposes the required task API paths `featurelifted.MarkerRegistry`, `featurelifted.MarkerRegistry.from_ini`, `featurelifted.MarkerRegistry.names`, `featurelifted.MarkerRegistry.add_line`, `featurelifted.MarkerRegistry.description`, `featurelifted.MarkerRegistry.from_lines`, `featurelifted.parse_linelist`, `featurelifted.split_marker_line` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pytest, _pytest.
<!-- featureliftbench:behavior-clauses:end -->
