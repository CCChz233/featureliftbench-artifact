# FeatureLift Task: Safe YAML load and dump

Extract a task-scoped subset of `yaml` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    constructor,
    safe_dump,
    safe_dump_all,
    safe_load,
    safe_load_all,
    YAMLError,
)
```

## Required API Details

- `safe_load(stream)`
- `safe_load_all(stream)`
- `safe_dump(data, stream=None, **kwds)`
- `safe_dump_all(documents, stream=None, **kwds)`
- `YAMLError` must be importable and raisable
- `constructor` module must be importable
  - `constructor.ConstructorError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse mappings, sequences, scalars, booleans, nulls, integers, floats, and nested documents. Required observable cases include safe load basic mapping sequence and scalars; unicode scalar and timestamp tag.
- The extracted feature must support this observable behavior: support anchors, aliases, and merge keys with SafeLoader semantics. Required observable cases include anchors aliases merge keys and dates.
- The extracted feature must support this observable behavior: dump plain Python data through SafeDumper with deterministic sort_keys behavior. Required observable cases include safe dump sort keys output; parse errors and flow style dumping.
- The extracted feature must support this observable behavior: load and dump multi-document streams. Required observable cases include multi document dump load and unsafe tags rejected; parse errors and flow style dumping.
- The extracted feature must support this observable behavior: reject unsafe Python object tags under safe_load. Required observable cases include safe load basic mapping sequence and scalars; multi document dump load and unsafe tags rejected; unicode scalar and timestamp tag.
- The package exposes the required task API paths `featurelifted.safe_load`, `featurelifted.safe_load_all`, `featurelifted.safe_dump`, `featurelifted.safe_dump_all`, `featurelifted.YAMLError`, `featurelifted.constructor`, `featurelifted.constructor.ConstructorError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `yaml`.
- Do not implement unsafe load/object construction APIs.
- Do not implement LibYAML C extension acceleration.
- Do not implement command line utilities and test fixtures.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse mappings, sequences, scalars, booleans, nulls, integers, floats, and nested documents. Required observable cases include safe load basic mapping sequence and scalars; unicode scalar and timestamp tag.
- **B002** — The extracted feature must support this observable behavior: support anchors, aliases, and merge keys with SafeLoader semantics. Required observable cases include anchors aliases merge keys and dates.
- **B003** — The extracted feature must support this observable behavior: dump plain Python data through SafeDumper with deterministic sort_keys behavior. Required observable cases include safe dump sort keys output; parse errors and flow style dumping.
- **B004** — The extracted feature must support this observable behavior: load and dump multi-document streams. Required observable cases include multi document dump load and unsafe tags rejected; parse errors and flow style dumping.
- **B005** — The extracted feature must support this observable behavior: reject unsafe Python object tags under safe_load. Required observable cases include safe load basic mapping sequence and scalars; multi document dump load and unsafe tags rejected; unicode scalar and timestamp tag.
- **B006** — The package exposes the required task API paths `featurelifted.safe_load`, `featurelifted.safe_load_all`, `featurelifted.safe_dump`, `featurelifted.safe_dump_all`, `featurelifted.YAMLError`, `featurelifted.constructor`, `featurelifted.constructor.ConstructorError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: yaml.
<!-- featureliftbench:behavior-clauses:end -->
