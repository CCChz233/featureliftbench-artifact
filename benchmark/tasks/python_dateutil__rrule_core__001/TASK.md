# FeatureLift Task: iCalendar recurrence (rrule) core

Extract a task-scoped subset of `dateutil` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    DAILY,
    FR,
    MO,
    MONTHLY,
    rrule,
    rruleset,
    rrulestr,
    SA,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    YEARLY,
)
```

## Required API Details

- `rrule` module must be importable
- `rruleset(cache=False)`
- `rrulestr(s, **kwargs)`
- `YEARLY` constant must exist
- `MONTHLY` constant must exist
- `WEEKLY` constant must exist
- `DAILY` constant must exist
- `MO` constant must exist
- `TU` constant must exist
- `WE` constant must exist
- `TH` constant must exist
- `FR` constant must exist
- `SA` constant must exist
- `SU` constant must exist

## Required Behavior

- The extracted feature must support this observable behavior: rrule iteration with freq, interval, count, until, and BY* filters. Required observable cases include weekly byweekday filter; count stops iteration; bysetpos last friday; invalid rrulestr freq raises.
- The extracted feature must support this observable behavior: rruleset include rules with EXDATE/RDATE (naive). Required observable cases include rrulestr parses monthly rule; rruleset exdate skips.
- The extracted feature must support this observable behavior: rrulestr for RRULE lines with naive iCalendar date values. Required observable cases include monthly rrule yields dates; rrulestr parses monthly rule; invalid rrulestr freq raises; rrulestr byday token.
- The extracted feature must support this observable behavior: BYEASTER offsets via easter helper. Required observable cases include byeaster occurrence.
- The extracted feature must support this observable behavior: weekday constants MO..SU and freq constants. Required observable cases include bysetpos last friday.
- The package exposes the required task API paths `featurelifted.rrule`, `featurelifted.rruleset`, `featurelifted.rrulestr`, `featurelifted.YEARLY`, `featurelifted.MONTHLY`, `featurelifted.WEEKLY`, `featurelifted.DAILY`, `featurelifted.MO`, `featurelifted.TU`, `featurelifted.WE`, `featurelifted.TH`, `featurelifted.FR`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `dateutil`.
- Do not implement dateutil.tz, TZID, zoneinfo, tzwin.
- Do not implement relativedelta and general dateutil.parser.
- Do not implement original dateutil package import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: rrule iteration with freq, interval, count, until, and BY* filters. Required observable cases include weekly byweekday filter; count stops iteration; bysetpos last friday; invalid rrulestr freq raises.
- **B002** — The extracted feature must support this observable behavior: rruleset include rules with EXDATE/RDATE (naive). Required observable cases include rrulestr parses monthly rule; rruleset exdate skips.
- **B003** — The extracted feature must support this observable behavior: rrulestr for RRULE lines with naive iCalendar date values. Required observable cases include monthly rrule yields dates; rrulestr parses monthly rule; invalid rrulestr freq raises; rrulestr byday token.
- **B004** — The extracted feature must support this observable behavior: BYEASTER offsets via easter helper. Required observable cases include byeaster occurrence.
- **B005** — The extracted feature must support this observable behavior: weekday constants MO..SU and freq constants. Required observable cases include bysetpos last friday.
- **B006** — The package exposes the required task API paths `featurelifted.rrule`, `featurelifted.rruleset`, `featurelifted.rrulestr`, `featurelifted.YEARLY`, `featurelifted.MONTHLY`, `featurelifted.WEEKLY`, `featurelifted.DAILY`, `featurelifted.MO`, `featurelifted.TU`, `featurelifted.WE`, `featurelifted.TH`, `featurelifted.FR`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: dateutil.
<!-- featureliftbench:behavior-clauses:end -->
