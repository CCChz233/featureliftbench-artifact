# FeatureLift Task: Astroid parse and nodes subset

Extract a task-scoped subset of `astroid` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    AsyncFunctionDef,
    ClassDef,
    FunctionDef,
    Match,
    parse,
)
```

## Required API Details

- `parse(code: 'str', module_name: 'str' = '', path: 'str | None' = None, apply_transforms: 'bool' = True) -> 'nodes.Module'`
- `ClassDef(name=None, doc: 'str | None' = None, lineno=None, col_offset=None, parent=None, *, end_lineno=None, end_col_offset=None)` class constructor
- `FunctionDef(name=None, doc: 'str | None' = None, lineno=None, col_offset=None, parent=None, *, end_lineno=None, end_col_offset=None)` class constructor
- `AsyncFunctionDef(name=None, doc: 'str | None' = None, lineno=None, col_offset=None, parent=None, *, end_lineno=None, end_col_offset=None)` class constructor
- `Match(lineno: 'int | None' = None, col_offset: 'int | None' = None, parent: 'NodeNG | None' = None, *, end_lineno: 'int | None' = None, end_col_offset: 'int | None' = None) -> 'None'` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: parse Python source into astroid Module trees. Required observable cases include parse function and class; module as string contains def.
- The extracted feature must support this observable behavior: rebuild functions, classes, async, and match statements. Required observable cases include async and match statements.
- The extracted feature must support this observable behavior: preserve docstrings, annotations, and default arguments. Required observable cases include defaults and docstring.
- The extracted feature must support this observable behavior: NodeNG as_string and basic structural attributes. Required observable cases include module as string contains def.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.ClassDef`, `featurelifted.FunctionDef`, `featurelifted.AsyncFunctionDef`, `featurelifted.Match` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `astroid`.
- Do not implement inference engine and brain module overrides.
- Do not implement live object introspection and import graph analysis.
- Do not implement pylint integration and original astroid import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse Python source into astroid Module trees. Required observable cases include parse function and class; module as string contains def.
- **B002** — The extracted feature must support this observable behavior: rebuild functions, classes, async, and match statements. Required observable cases include async and match statements.
- **B003** — The extracted feature must support this observable behavior: preserve docstrings, annotations, and default arguments. Required observable cases include defaults and docstring.
- **B004** — The extracted feature must support this observable behavior: NodeNG as_string and basic structural attributes. Required observable cases include module as string contains def.
- **B005** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.ClassDef`, `featurelifted.FunctionDef`, `featurelifted.AsyncFunctionDef`, `featurelifted.Match` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: astroid.
<!-- featureliftbench:behavior-clauses:end -->
