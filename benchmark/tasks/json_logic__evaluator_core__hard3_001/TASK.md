# FeatureLift Task: JSON logic evaluator with variable resolution

Extract a task-scoped subset of `json_logic` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    jsonLogic,
)
```

## Required API Details

- `jsonLogic(tests, data=None)`

## Required Behavior

- When jsonLogic evaluates supported arithmetic, comparison, conditional, collection, and boolean rules, it returns the corresponding JSON-compatible result.
- When a var rule uses dotted paths or a default, jsonLogic resolves nested data and returns the default for missing paths.
- When and/or rules are evaluated, operands short-circuit in order and return the same operand-style result as the upstream semantics.
- The package exposes the required task API paths `featurelifted.jsonLogic` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `json_logic`.
- Forbidden path access: `repo/, json_logic/`.
- Do not implement network access.
- Do not implement original repository import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When jsonLogic evaluates supported arithmetic, comparison, conditional, collection, and boolean rules, it returns the corresponding JSON-compatible result.
- **B002** — When a var rule uses dotted paths or a default, jsonLogic resolves nested data and returns the default for missing paths.
- **B003** — When and/or rules are evaluated, operands short-circuit in order and return the same operand-style result as the upstream semantics.
- **B004** — The package exposes the required task API paths `featurelifted.jsonLogic` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: json_logic.
<!-- featureliftbench:behavior-clauses:end -->
