# FeatureLift Task: relativedelta arithmetic core

Extract a task-scoped subset of `dateutil` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    FR,
    MO,
    relativedelta,
    SA,
    SU,
    TH,
    TU,
    WE,
)
```

## Required API Details

- `relativedelta` module must be importable
- `MO` constant must exist
- `TU` constant must exist
- `WE` constant must exist
- `TH` constant must exist
- `FR` constant must exist
- `SA` constant must exist
- `SU` constant must exist
- `MO.weekday` attribute must exist

## Required Behavior

- The extracted feature must support this observable behavior: relativedelta construction with relative and absolute fields. Required observable cases include absolute day replacement; subtract relativedelta.
- The extracted feature must support this observable behavior: datetime/date addition and subtraction with month/year rollover. Required observable cases include add months to datetime; relativedelta diff months; last friday of month; yearday sets month day; non integer years months rejected.
- The extracted feature must support this observable behavior: weekday nth helpers MO..SU with setpos semantics. Required observable cases include weekday constant identity; weekday nth first monday.
- The extracted feature must support this observable behavior: normalized() for fractional day/hour cascading. Required observable cases include add days and hours; absolute day replacement; normalized fractional days.
- The extracted feature must support this observable behavior: relativedelta(dt1, dt2) difference mode. Required observable cases include relativedelta diff months; subtract relativedelta.
- The extracted feature must support this observable behavior: yearday/nlyearday and leapdays adjustments. Required observable cases include yearday sets month day; leapdays post february.
- The package exposes the required task API paths `featurelifted.relativedelta`, `featurelifted.MO`, `featurelifted.TU`, `featurelifted.WE`, `featurelifted.TH`, `featurelifted.FR`, `featurelifted.SA`, `featurelifted.SU`, `featurelifted.MO.weekday` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `dateutil`.
- Do not implement dateutil.rrule, rrulestr, rruleset.
- Do not implement dateutil.parser and general string date parsing.
- Do not implement dateutil.tz, zoneinfo, tzwin.
- Do not implement original dateutil package import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: relativedelta construction with relative and absolute fields. Required observable cases include absolute day replacement; subtract relativedelta.
- **B002** — The extracted feature must support this observable behavior: datetime/date addition and subtraction with month/year rollover. Required observable cases include add months to datetime; relativedelta diff months; last friday of month; yearday sets month day; non integer years months rejected.
- **B003** — The extracted feature must support this observable behavior: weekday nth helpers MO..SU with setpos semantics. Required observable cases include weekday constant identity; weekday nth first monday.
- **B004** — The extracted feature must support this observable behavior: normalized() for fractional day/hour cascading. Required observable cases include add days and hours; absolute day replacement; normalized fractional days.
- **B005** — The extracted feature must support this observable behavior: relativedelta(dt1, dt2) difference mode. Required observable cases include relativedelta diff months; subtract relativedelta.
- **B006** — The extracted feature must support this observable behavior: yearday/nlyearday and leapdays adjustments. Required observable cases include yearday sets month day; leapdays post february.
- **B007** — The package exposes the required task API paths `featurelifted.relativedelta`, `featurelifted.MO`, `featurelifted.TU`, `featurelifted.WE`, `featurelifted.TH`, `featurelifted.FR`, `featurelifted.SA`, `featurelifted.SU`, `featurelifted.MO.weekday` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: dateutil.
<!-- featureliftbench:behavior-clauses:end -->
