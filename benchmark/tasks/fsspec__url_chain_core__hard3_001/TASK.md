# FeatureLift Task: url_to_fs

Extract a task-scoped subset of `fsspec` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ProtocolRegistry,
    UnknownProtocolError,
    url_to_fs,
)
```

## Required API Details

- `ProtocolRegistry() -> 'None'` class constructor
- `url_to_fs(url: 'str', registry: 'ProtocolRegistry') -> 'tuple[str, str, dict[str, Any]]'`
- `UnknownProtocolError` must be importable and raisable

## Required Behavior

- `ProtocolRegistry` resolves protocol names and aliases.
- url_to_fs parses chained URLs and merges query/storage options, including decoding a storage_options=key=value query item into a top-level option such as options["anon"] == "true" for ?storage_options=anon=true.
- Unknown protocols raise `UnknownProtocolError`.
- The package exposes the required task API paths `featurelifted.ProtocolRegistry`, `featurelifted.url_to_fs`, `featurelifted.UnknownProtocolError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `fsspec`.
- Forbidden path access: `repo/, fsspec/`.
- Do not implement network access.
- Do not implement remote filesystem implementations.
- Do not implement async code.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `ProtocolRegistry` resolves protocol names and aliases.
- **B002** — url_to_fs parses chained URLs and merges query/storage options, including decoding a storage_options=key=value query item into a top-level option such as options["anon"] == "true" for ?storage_options=anon=true.
- **B003** — Unknown protocols raise `UnknownProtocolError`.
- **B004** — The package exposes the required task API paths `featurelifted.ProtocolRegistry`, `featurelifted.url_to_fs`, `featurelifted.UnknownProtocolError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: fsspec.
<!-- featureliftbench:behavior-clauses:end -->
