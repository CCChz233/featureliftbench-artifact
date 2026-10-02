# FeatureLift Task: Schema validation core

Extract a task-scoped subset of `cerberus` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    DocumentError,
    SchemaError,
    Validator,
)
```

## Required API Details

- `Validator(*args, **kwargs)` class constructor
  - `Validator.document` attribute must exist on instances
  - `Validator.errors` attribute must exist on instances
  - `Validator.validate(self, document, schema=None, update=False, normalize=True)`
- `DocumentError` must be importable and raisable
- `SchemaError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: validate dict documents against nested schema definitions. Required observable cases include validate returns bool; nested schema validation; coerce updates document; deep nested schema and coerce combo.
- The extracted feature must support this observable behavior: enforce required fields and type rules on nested mappings and lists. Required observable cases include required field rejects missing; type rule rejects wrong type; nested list error paths.
- The extracted feature must support this observable behavior: coerce field values during validation and reflect coerced document. Required observable cases include coerce updates document.
- The extracted feature must support this observable behavior: aggregate nested validation failures into structured error trees. Required observable cases include nested schema validation; nested list error paths.
- The package exposes the required task API paths `featurelifted.Validator`, `featurelifted.Validator.document`, `featurelifted.Validator.errors`, `featurelifted.Validator.validate`, `featurelifted.DocumentError`, `featurelifted.SchemaError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `cerberus`.
- Do not implement schema_registry and rules_set_registry named schema indirection.
- Do not implement normalization rename/default pipelines beyond coerce in tests.
- Do not implement benchmarks, upstream tests, docs, and packaging metadata.
- Do not implement original cerberus import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: validate dict documents against nested schema definitions. Required observable cases include validate returns bool; nested schema validation; coerce updates document; deep nested schema and coerce combo.
- **B002** — The extracted feature must support this observable behavior: enforce required fields and type rules on nested mappings and lists. Required observable cases include required field rejects missing; type rule rejects wrong type; nested list error paths.
- **B003** — The extracted feature must support this observable behavior: coerce field values during validation and reflect coerced document. Required observable cases include coerce updates document.
- **B004** — The extracted feature must support this observable behavior: aggregate nested validation failures into structured error trees. Required observable cases include nested schema validation; nested list error paths.
- **B005** — The package exposes the required task API paths `featurelifted.Validator`, `featurelifted.Validator.document`, `featurelifted.Validator.errors`, `featurelifted.Validator.validate`, `featurelifted.DocumentError`, `featurelifted.SchemaError` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: cerberus.
<!-- featureliftbench:behavior-clauses:end -->
