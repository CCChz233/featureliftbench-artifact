# FeatureLift Task: Datetime parse, format, and duration core

Extract a task-scoped subset of `pendulum` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Date,
    DateTime,
    datetime,
    Duration,
    duration,
    fixed_timezone,
    parse,
    ParserError,
    Time,
    UTC,
)
```

## Required API Details

- `UTC` constant must exist
- `Date(*args, **kwargs)` class constructor
  - `Date.day` attribute must exist on instances
  - `Date.hour` attribute must exist on instances
  - `Date.minute` attribute must exist on instances
  - `Date.month` attribute must exist on instances
  - `Date.year` attribute must exist on instances
- `DateTime(*args, **kwargs)` class constructor
  - `DateTime.hour` attribute must exist on instances
  - `DateTime.microsecond` attribute must exist on instances
  - `DateTime.minute` attribute must exist on instances
  - `DateTime.offset` attribute must exist on instances
- `Duration(days: 'float' = 0, seconds: 'float' = 0, microseconds: 'float' = 0, milliseconds: 'float' = 0, minutes: 'float' = 0, hours: 'float' = 0, weeks: 'float' = 0, years: 'float' = 0, months: 'float' = 0) -> 'Self'` class constructor
  - `Duration.hours` attribute must exist on instances
  - `Duration.in_days(self) -> 'int'`
  - `Duration.minutes` attribute must exist on instances
  - `Duration.months` attribute must exist on instances
  - `Duration.remaining_days` attribute must exist on instances
  - `Duration.remaining_seconds` attribute must exist on instances
  - `Duration.weeks` attribute must exist on instances
  - `Duration.years` attribute must exist on instances
- `ParserError` must be importable and raisable
- `Time(*args, **kwargs)` class constructor
- `datetime` module must be importable
- `duration` module must be importable
- `fixed_timezone(offset: 'int') -> 'FixedTimezone'`
- `parse(text: 'str', **options: 't.Any') -> 'Date | Time | DateTime | Duration'`

## Required Behavior

- The extracted feature must support this observable behavior: parse ISO8601 dates, datetimes with Z or numeric offsets, and durations. Required observable cases include parse iso date; parse iso datetime zulu; parse iso duration; parse iso week calendar date; parse duration weeks component; parse duration full components; parse fixed offset without colon; parse subsecond truncation; parse invalid iso raises.
- The extracted feature must support this observable behavior: parse common YYYY-MM-DD and HH:mm:ss combinations. Required observable cases include parse common day first; parse subsecond truncation; parse invalid iso raises.
- The extracted feature must support this observable behavior: construct DateTime and Duration instances. Required observable cases include parse subsecond truncation.
- The extracted feature must support this observable behavior: format datetimes with Pendulum tokens (YYYY, MM, DD, HH, mm, ss, Z). Required observable cases include datetime format tokens; format literal brackets.
- The extracted feature must support this observable behavior: duration component properties (years, months, weeks, days, hours, minutes, seconds). Required observable cases include duration constructor and total seconds; parse duration weeks component; parse duration full components; duration years months not float.
- The package exposes the required task API paths `featurelifted.UTC`, `featurelifted.Date`, `featurelifted.Date.day`, `featurelifted.Date.hour`, `featurelifted.Date.minute`, `featurelifted.Date.month`, `featurelifted.Date.year`, `featurelifted.DateTime`, `featurelifted.DateTime.hour`, `featurelifted.DateTime.microsecond`, `featurelifted.DateTime.minute`, `featurelifted.DateTime.offset`, and 15 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pendulum`.
- Do not implement bundled tzdata or IANA timezone database traversal.
- Do not implement named timezone scheduling (Europe/Paris, America/New_York, etc.).
- Do not implement humanize/diff-for-humans and locale packs beyond English.
- Do not implement interval iteration, now()/travel mocking, and CLI.
- Do not implement original pendulum import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse ISO8601 dates, datetimes with Z or numeric offsets, and durations. Required observable cases include parse iso date; parse iso datetime zulu; parse iso duration; parse iso week calendar date; parse duration weeks component; parse duration full components; parse fixed offset without colon; parse subsecond truncation; parse invalid iso raises.
- **B002** — The extracted feature must support this observable behavior: parse common YYYY-MM-DD and HH:mm:ss combinations. Required observable cases include parse common day first; parse subsecond truncation; parse invalid iso raises.
- **B003** — The extracted feature must support this observable behavior: construct DateTime and Duration instances. Required observable cases include parse subsecond truncation.
- **B004** — The extracted feature must support this observable behavior: format datetimes with Pendulum tokens (YYYY, MM, DD, HH, mm, ss, Z). Required observable cases include datetime format tokens; format literal brackets.
- **B005** — The extracted feature must support this observable behavior: duration component properties (years, months, weeks, days, hours, minutes, seconds). Required observable cases include duration constructor and total seconds; parse duration weeks component; parse duration full components; duration years months not float.
- **B006** — The package exposes the required task API paths `featurelifted.UTC`, `featurelifted.Date`, `featurelifted.Date.day`, `featurelifted.Date.hour`, `featurelifted.Date.minute`, `featurelifted.Date.month`, `featurelifted.Date.year`, `featurelifted.DateTime`, `featurelifted.DateTime.hour`, `featurelifted.DateTime.microsecond`, `featurelifted.DateTime.minute`, `featurelifted.DateTime.offset`, and 15 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pendulum.
<!-- featureliftbench:behavior-clauses:end -->
