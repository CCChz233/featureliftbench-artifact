# FeatureLift Task: JSON5 parse and loads

Extract a task-scoped subset of `json5` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    load,
    loads,
)
```

## Required API Details

- `loads(s, encoding=None, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, allow_duplicate_keys=True)`
- `load(fp, encoding=None, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, allow_duplicate_keys=True)`

## Required Behavior

- The extracted feature must support this observable behavior: parse JSON5 objects, arrays, strings, numbers, booleans, and null. Required observable cases include malformed input reports position.
- The extracted feature must support this observable behavior: support unquoted keys, single-quoted strings, trailing commas, and comments. Required observable cases include loads parses unquoted keys and trailing comma; loads supports line comments; malformed input reports position.
- The extracted feature must support this observable behavior: support hexadecimal and leading-plus numeric literals. Required observable cases include hex and plus numeric literals.
- The extracted feature must support this observable behavior: raise ValueError with line/column context for malformed input. Required observable cases include malformed input reports position.
- The extracted feature must support this observable behavior: optional duplicate-key rejection via allow_duplicate_keys=False. Required observable cases include duplicate keys rejected when disabled.
- The package exposes the required task API paths `featurelifted.loads`, `featurelifted.load` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `json5`.
- Do not implement json5 dump/dumps serialization.
- Do not implement CLI tool and arg_parser modules.
- Do not implement original project tests and documentation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse JSON5 objects, arrays, strings, numbers, booleans, and null. Required observable cases include malformed input reports position.
- **B002** — The extracted feature must support this observable behavior: support unquoted keys, single-quoted strings, trailing commas, and comments. Required observable cases include loads parses unquoted keys and trailing comma; loads supports line comments; malformed input reports position.
- **B003** — The extracted feature must support this observable behavior: support hexadecimal and leading-plus numeric literals. Required observable cases include hex and plus numeric literals.
- **B004** — The extracted feature must support this observable behavior: raise ValueError with line/column context for malformed input. Required observable cases include malformed input reports position.
- **B005** — The extracted feature must support this observable behavior: optional duplicate-key rejection via allow_duplicate_keys=False. Required observable cases include duplicate keys rejected when disabled.
- **B006** — The package exposes the required task API paths `featurelifted.loads`, `featurelifted.load` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: json5.
<!-- featureliftbench:behavior-clauses:end -->
