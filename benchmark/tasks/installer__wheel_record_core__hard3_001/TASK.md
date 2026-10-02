# FeatureLift Task: parse_wheel_record find_dist_info

Extract a task-scoped subset of `installer` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    find_dist_info,
    parse_wheel_record,
    script_name,
)
```

## Required API Details

- `parse_wheel_record(content: 'str') -> 'list[tuple[str, str | None, int | None]]'`
- `find_dist_info(names: 'list[str]') -> 'str | None'`
- `script_name(entry_point: 'str') -> 'str'`

## Required Behavior

- `parse_wheel_record` parses CSV RECORD rows into `(path, digest, size)` tuples.
- `find_dist_info` locates a unique `.dist-info` directory among archive names.
- `script_name` derives console script names from entry point targets.
- The package exposes the required task API paths `featurelifted.parse_wheel_record`, `featurelifted.find_dist_info`, `featurelifted.script_name` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `installer`.
- Forbidden path access: `repo/, installer/`.
- Do not implement network access.
- Do not implement filesystem install destinations.
- Do not implement subprocess.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `parse_wheel_record` parses CSV RECORD rows into `(path, digest, size)` tuples.
- **B002** — `find_dist_info` locates a unique `.dist-info` directory among archive names.
- **B003** — `script_name` derives console script names from entry point targets.
- **B004** — The package exposes the required task API paths `featurelifted.parse_wheel_record`, `featurelifted.find_dist_info`, `featurelifted.script_name` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: installer.
<!-- featureliftbench:behavior-clauses:end -->
