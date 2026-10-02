# FeatureLift Task: ZoneResolver

Extract a task-scoped subset of `dateutil` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    InvalidTZFileError,
    parse_tzfile,
    UnknownZoneError,
    ZoneResolver,
)
```

## Required API Details

- `ZoneResolver() -> 'None'` class constructor
  - `ZoneResolver.load_zone(self, name: 'str', tzdata: 'dict[str, bytes]') -> 'TZZone'`
  - `ZoneResolver.get(self, name: 'str') -> 'TZZone'`
  - `ZoneResolver.register_alias(self, alias: 'str', canonical: 'str') -> 'None'`
- `parse_tzfile(data: 'bytes') -> 'dict[str, int]'`
- `UnknownZoneError` must be importable and raisable
- `InvalidTZFileError` must be importable and raisable

## Required Behavior

- `parse_tzfile` validates tzfile headers and extracts metadata.
- Aliases resolve to canonical zone names with cycle detection.
- When a zone alias is resolved, ZoneResolver follows aliases to the canonical zone and raises UnknownZoneError for missing names or alias cycles.
- The package exposes the required task API paths `featurelifted.ZoneResolver`, `featurelifted.ZoneResolver.load_zone`, `featurelifted.ZoneResolver.get`, `featurelifted.ZoneResolver.register_alias`, `featurelifted.parse_tzfile`, `featurelifted.UnknownZoneError`, `featurelifted.InvalidTZFileError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `dateutil`.
- Forbidden path access: `repo/, dateutil/`.
- Do not implement network access.
- Do not implement tzdata download.
- Do not implement full datetime tz conversion.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `parse_tzfile` validates tzfile headers and extracts metadata.
- **B002** — Aliases resolve to canonical zone names with cycle detection.
- **B003** — When a zone alias is resolved, ZoneResolver follows aliases to the canonical zone and raises UnknownZoneError for missing names or alias cycles.
- **B004** — The package exposes the required task API paths `featurelifted.ZoneResolver`, `featurelifted.ZoneResolver.load_zone`, `featurelifted.ZoneResolver.get`, `featurelifted.ZoneResolver.register_alias`, `featurelifted.parse_tzfile`, `featurelifted.UnknownZoneError`, `featurelifted.InvalidTZFileError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: dateutil.
<!-- featureliftbench:behavior-clauses:end -->
