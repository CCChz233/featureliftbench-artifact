# FeatureLift Task: Humanize natural time and delta formatting

Extract a task-scoped subset of `humanize` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    naturaldate,
    naturalday,
    naturaldelta,
    naturaltime,
    precisedelta,
)
```

## Required API Details

- `naturaltime(value: 'dt.datetime | dt.timedelta | float', future: 'bool' = False, months: 'bool' = True, minimum_unit: 'str' = 'seconds', when: 'dt.datetime | None' = None) -> 'str'`
- `naturaldelta(value: 'dt.timedelta | float', months: 'bool' = True, minimum_unit: 'str' = 'seconds') -> 'str'`
- `naturaldate(value: 'dt.date | dt.datetime') -> 'str'`
- `naturalday(value: 'dt.date | dt.datetime', format: 'str' = '%b %d') -> 'str'`
- `precisedelta(value: 'dt.timedelta | float | None', minimum_unit: 'str' = 'seconds', suppress: 'Iterable[str]' = (), format: 'str' = '%0.2f') -> 'str'`

## Required Behavior

- The extracted feature must support this observable behavior: naturaltime relative phrasing with when=. Required observable cases include naturaltime past with when; naturaltime future with when; naturaltime two hour past.
- The extracted feature must support this observable behavior: naturaldelta month/year granularity. Required observable cases include naturaldelta hours; naturaldate distant year; naturaldelta long month granularity.
- The extracted feature must support this observable behavior: precisedelta suppress and minimum_unit. Required observable cases include precisedelta suppress days.
- The extracted feature must support this observable behavior: naturaldate and naturalday phrasing. Required observable cases include naturaldate distant year; naturalday today label.
- The package exposes the required task API paths `featurelifted.naturaltime`, `featurelifted.naturaldelta`, `featurelifted.naturaldate`, `featurelifted.naturalday`, `featurelifted.precisedelta` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `humanize`.
- Do not implement filesize/lists/number formatting beyond time deps.
- Do not implement non-English locale packs.
- Do not implement original humanize import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: naturaltime relative phrasing with when=. Required observable cases include naturaltime past with when; naturaltime future with when; naturaltime two hour past.
- **B002** — The extracted feature must support this observable behavior: naturaldelta month/year granularity. Required observable cases include naturaldelta hours; naturaldate distant year; naturaldelta long month granularity.
- **B003** — The extracted feature must support this observable behavior: precisedelta suppress and minimum_unit. Required observable cases include precisedelta suppress days.
- **B004** — The extracted feature must support this observable behavior: naturaldate and naturalday phrasing. Required observable cases include naturaldate distant year; naturalday today label.
- **B005** — The package exposes the required task API paths `featurelifted.naturaltime`, `featurelifted.naturaldelta`, `featurelifted.naturaldate`, `featurelifted.naturalday`, `featurelifted.precisedelta` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: humanize.
<!-- featureliftbench:behavior-clauses:end -->
