# FeatureLift Task: ISO8601 duration parse and format

Extract a task-scoped subset of `isodate` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Duration,
    duration_isoformat,
    ISO8601Error,
    isodates,
    parse_duration,
)
```

## Required API Details

- `Duration(days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0, months=0, years=0)` class constructor
  - `Duration.months` attribute must exist on instances
  - `Duration.tdelta` attribute must exist on instances
  - `Duration.totimedelta(self, start=None, end=None)`
  - `Duration.years` attribute must exist on instances
- `ISO8601Error` must be importable and raisable
- `duration_isoformat(tduration, format='P%P')`
- `parse_duration(datestring, as_timedelta_if_possible=True)`
- `isodates` module must be importable
  - `isodates.parse_date(datestring, yeardigits=4, expanded=False, defaultmonth=1, defaultday=1)`

## Required Behavior

- The extracted feature must support this observable behavior: parse P-period durations to timedelta or Duration. Required observable cases include parse duration days hours; parse duration weeks; parse duration full components; parse duration comma decimal hours; duration totimedelta with start; duration isoformat timedelta; parse invalid raises.
- The extracted feature must support this observable behavior: duration_isoformat for Duration and timedelta. Required observable cases include duration isoformat; duration totimedelta with start; duration isoformat timedelta.
- The extracted feature must support this observable behavior: decimal comma fractions in components. Required observable cases include parse duration comma decimal hours.
- The extracted feature must support this observable behavior: ISO8601Error on invalid input. Required observable cases include parse invalid raises.
- The package exposes the required task API paths `featurelifted.Duration`, `featurelifted.Duration.months`, `featurelifted.Duration.tdelta`, `featurelifted.Duration.totimedelta`, `featurelifted.Duration.years`, `featurelifted.ISO8601Error`, `featurelifted.duration_isoformat`, `featurelifted.parse_duration`, `featurelifted.isodates`, `featurelifted.isodates.parse_date` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `isodate`.
- Do not implement full date/time/tz parsing surface.
- Do not implement strftime locale tables beyond duration chain.
- Do not implement original isodate import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse P-period durations to timedelta or Duration. Required observable cases include parse duration days hours; parse duration weeks; parse duration full components; parse duration comma decimal hours; duration totimedelta with start; duration isoformat timedelta; parse invalid raises.
- **B002** — The extracted feature must support this observable behavior: duration_isoformat for Duration and timedelta. Required observable cases include duration isoformat; duration totimedelta with start; duration isoformat timedelta.
- **B003** — The extracted feature must support this observable behavior: decimal comma fractions in components. Required observable cases include parse duration comma decimal hours.
- **B004** — The extracted feature must support this observable behavior: ISO8601Error on invalid input. Required observable cases include parse invalid raises.
- **B005** — The package exposes the required task API paths `featurelifted.Duration`, `featurelifted.Duration.months`, `featurelifted.Duration.tdelta`, `featurelifted.Duration.totimedelta`, `featurelifted.Duration.years`, `featurelifted.ISO8601Error`, `featurelifted.duration_isoformat`, `featurelifted.parse_duration`, `featurelifted.isodates`, `featurelifted.isodates.parse_date` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: isodate.
<!-- featureliftbench:behavior-clauses:end -->
