# FeatureLift Task: Wheel metadata normalization helpers

Extract a task-scoped subset of `wheel` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    parse_wheel_filename,
    safe_extra,
    safe_name,
    split_sections,
    urlsafe_b64encode,
    WheelError,
)
```

## Required API Details

- `safe_name(name: 'str') -> 'str'`
- `safe_extra(extra: 'str') -> 'str'`
- `split_sections(text: 'str') -> 'list[tuple[str | None, list[str]]]'`
- `parse_wheel_filename(filename: 'str') -> 'tuple[str, str, str]'`
- `urlsafe_b64encode(data: 'bytes') -> 'bytes'`
- `WheelError` must be importable and raisable

## Required Behavior

- safe_name and safe_extra normalize project names and extras into their canonical metadata-safe forms.
- parse_wheel_filename returns a 3-tuple of normalized distribution name, version, and build tag, and raises WheelError for invalid filenames.
- split_sections separates metadata headers from named body sections without losing section content or order.
- The package exposes the required task API paths `featurelifted.safe_name`, `featurelifted.safe_extra`, `featurelifted.split_sections`, `featurelifted.parse_wheel_filename`, `featurelifted.urlsafe_b64encode`, `featurelifted.WheelError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `wheel`.
- Forbidden path access: `repo/, wheel/`.
- Do not implement network access.
- Do not implement wheel pack/unpack execution.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — safe_name and safe_extra normalize project names and extras into their canonical metadata-safe forms.
- **B002** — parse_wheel_filename returns a 3-tuple of normalized distribution name, version, and build tag, and raises WheelError for invalid filenames.
- **B003** — split_sections separates metadata headers from named body sections without losing section content or order.
- **B004** — The package exposes the required task API paths `featurelifted.safe_name`, `featurelifted.safe_extra`, `featurelifted.split_sections`, `featurelifted.parse_wheel_filename`, `featurelifted.urlsafe_b64encode`, `featurelifted.WheelError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: wheel.
<!-- featureliftbench:behavior-clauses:end -->
