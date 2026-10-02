# FeatureLift Task: Resource finder and wheel RECORD path normalization

Extract a task-scoped subset of `distlib` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    normalize_record_path,
    parse_record,
    to_posix,
    validate_record_hash,
)
```

## Required API Details

- `to_posix(path: 'str') -> 'str'`
- `normalize_record_path(path: 'str') -> 'str'`
- `parse_record(content: 'str') -> 'list[tuple[str, str | None, int | None]]'`
- `validate_record_hash(path: 'str', digest: 'str | None') -> 'bool'`

## Required Behavior

- `parse_record` parses CSV RECORD rows into `(path, digest, size)` tuples.
- `normalize_record_path` applies posix normalization and strips `./` prefixes.
- When validate_record_hash(path, digest) receives a RECORD digest string, it returns True for a well-formed supported hash such as sha256 followed by 64 hex characters and returns False for malformed or unsupported digest strings; the path argument identifies the RECORD path and does not have to exist on disk.
- The package exposes the required task API paths `featurelifted.to_posix`, `featurelifted.normalize_record_path`, `featurelifted.parse_record`, `featurelifted.validate_record_hash` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `distlib`.
- Forbidden path access: `repo/, distlib/`.
- Do not implement network access.
- Do not implement installers/locators.
- Do not implement script generation.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `parse_record` parses CSV RECORD rows into `(path, digest, size)` tuples.
- **B002** — `normalize_record_path` applies posix normalization and strips `./` prefixes.
- **B003** — When validate_record_hash(path, digest) receives a RECORD digest string, it returns True for a well-formed supported hash such as sha256 followed by 64 hex characters and returns False for malformed or unsupported digest strings; the path argument identifies the RECORD path and does not have to exist on disk.
- **B004** — The package exposes the required task API paths `featurelifted.to_posix`, `featurelifted.normalize_record_path`, `featurelifted.parse_record`, `featurelifted.validate_record_hash` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: distlib.
<!-- featureliftbench:behavior-clauses:end -->
