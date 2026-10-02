# FeatureLift Task: Cron trigger next-fire-time state

Extract a task-scoped subset of `apscheduler` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CronTrigger,
)
```

## Required API Details

- `CronTrigger(*, minute: 'str | int' = '*', hour: 'str | int' = '*', day: 'str | int' = '*', month: 'str | int' = '*', day_of_week: 'str | int' = '*', start_time: 'datetime | None' = None, end_time: 'datetime | None' = None) -> 'None'` class constructor
  - `CronTrigger.get_next_fire_time(self, now: 'datetime | None' = None) -> 'datetime | None'`

## Required Behavior

- When CronTrigger receives supported cron expressions, it parses wildcard, range, list, and step field forms into matching constraints.
- When get_next_fire_time is called, it returns the first matching datetime after now while advancing across cron fields deterministically.
- When a computed fire time would exceed end_time, get_next_fire_time returns no result; start_time remains the lower boundary.
- The package exposes the required task API paths `featurelifted.CronTrigger`, `featurelifted.CronTrigger.get_next_fire_time` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `apscheduler`.
- Forbidden path access: `repo/, apscheduler/`.
- Do not implement network access.
- Do not implement scheduler stores/executors.
- Do not implement subprocess.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When CronTrigger receives supported cron expressions, it parses wildcard, range, list, and step field forms into matching constraints.
- **B002** — When get_next_fire_time is called, it returns the first matching datetime after now while advancing across cron fields deterministically.
- **B003** — When a computed fire time would exceed end_time, get_next_fire_time returns no result; start_time remains the lower boundary.
- **B004** — The package exposes the required task API paths `featurelifted.CronTrigger`, `featurelifted.CronTrigger.get_next_fire_time` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: apscheduler.
<!-- featureliftbench:behavior-clauses:end -->
