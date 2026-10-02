# FeatureLift Task: Python parser grammar core

Extract a task-scoped subset of `parso` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Grammar,
    load_grammar,
    parse,
)
```

## Required API Details

- `parse(code=None, **kwargs)`
- `load_grammar(*, version: str = None, path: str = None)`
- `Grammar(text: str, *, tokenizer, parser=<class 'BaseParser'>, diff_parser=None)` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: parse Python source to syntax tree. Required observable cases include parse simple expr; parse version 39; error recovery partial tree.
- The extracted feature must support this observable behavior: get_code round-trip on nodes. Required observable cases include name node positions; get code roundtrip.
- The extracted feature must support this observable behavior: iter_errors for multiple syntax issues. Required observable cases include iter errors multiple; error recovery partial tree.
- The extracted feature must support this observable behavior: version-specific grammars. Required observable cases include parse version 39.
- The package exposes the required task API paths `featurelifted.parse`, `featurelifted.load_grammar`, `featurelifted.Grammar` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `parso`.
- Do not implement diff parser.
- Do not implement pep8 normalizer.
- Do not implement original parso import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse Python source to syntax tree. Required observable cases include parse simple expr; parse version 39; error recovery partial tree.
- **B002** — The extracted feature must support this observable behavior: get_code round-trip on nodes. Required observable cases include name node positions; get code roundtrip.
- **B003** — The extracted feature must support this observable behavior: iter_errors for multiple syntax issues. Required observable cases include iter errors multiple; error recovery partial tree.
- **B004** — The extracted feature must support this observable behavior: version-specific grammars. Required observable cases include parse version 39.
- **B005** — The package exposes the required task API paths `featurelifted.parse`, `featurelifted.load_grammar`, `featurelifted.Grammar` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: parso.
<!-- featureliftbench:behavior-clauses:end -->
