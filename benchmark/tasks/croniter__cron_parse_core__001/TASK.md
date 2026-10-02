# FeatureLift Task: Cron expression parse and next/prev iteration

Extract a task-scoped subset of `croniter` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    croniter,
    CroniterBadCronError,
    CroniterBadDateError,
    CroniterNotAlphaError,
    datetime_to_timestamp,
)
```

## Required API Details

- `croniter(expr_format, start_time=None, ret_type=<class 'float'>, day_or=True, max_years_between_matches=None, is_prev=False, hash_id=None, implement_cron_bug=False, second_at_beginning=None, expand_from_start_time=False)`
- `datetime_to_timestamp(d)`
- `CroniterBadCronError` must be importable and raisable
- `CroniterBadDateError` must be importable and raisable
- `CroniterNotAlphaError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse standard 5-field cron expressions. Required observable cases include weekday field parses; step and range fields.
- The extracted feature must support this observable behavior: compute next matching naive datetime from a base time. Required observable cases include daily noon next; daily noon prev; hourly on base minute; combined next prev walk; dom dow union next.
- The extracted feature must support this observable behavior: compute previous matching naive datetime from a base time. Required observable cases include daily noon prev; hourly on base minute; step and range fields.
- The extracted feature must support this observable behavior: step and range field expansion (e.g. */15, 9-17). Required observable cases include step and range fields.
- The extracted feature must support this observable behavior: reject invalid field values with CroniterBadCronError. Required observable cases include invalid minute raises.
- The package exposes the required task API paths `featurelifted.croniter`, `featurelifted.datetime_to_timestamp`, `featurelifted.CroniterBadCronError`, `featurelifted.CroniterBadDateError`, `featurelifted.CroniterNotAlphaError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `croniter`.
- Do not implement croniter_range generator.
- Do not implement hash/random H() field expansion.
- Do not implement match_range and is_valid helpers.
- Do not implement original croniter import at runtime.
- Do not implement timezone/DST-aware scheduling (tests use naive datetimes only).

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse standard 5-field cron expressions. Required observable cases include weekday field parses; step and range fields.
- **B002** — The extracted feature must support this observable behavior: compute next matching naive datetime from a base time. Required observable cases include daily noon next; daily noon prev; hourly on base minute; combined next prev walk; dom dow union next.
- **B003** — The extracted feature must support this observable behavior: compute previous matching naive datetime from a base time. Required observable cases include daily noon prev; hourly on base minute; step and range fields.
- **B004** — The extracted feature must support this observable behavior: step and range field expansion (e.g. */15, 9-17). Required observable cases include step and range fields.
- **B005** — The extracted feature must support this observable behavior: reject invalid field values with CroniterBadCronError. Required observable cases include invalid minute raises.
- **B006** — The package exposes the required task API paths `featurelifted.croniter`, `featurelifted.datetime_to_timestamp`, `featurelifted.CroniterBadCronError`, `featurelifted.CroniterBadDateError`, `featurelifted.CroniterNotAlphaError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: croniter.
<!-- featureliftbench:behavior-clauses:end -->
