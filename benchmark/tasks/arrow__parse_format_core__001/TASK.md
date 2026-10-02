# FeatureLift Task: Arrow parse, format, and humanize subset

Extract a task-scoped subset of `arrow` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Arrow,
    get,
)
```

## Required API Details

- `Arrow(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, microsecond: int = 0, tzinfo: Union[datetime.tzinfo, str, NoneType] = None, **kwargs: Any) -> None` class constructor
  - `Arrow.day` attribute must exist on instances
  - `Arrow.format(self, fmt: str = 'YYYY-MM-DD HH:mm:ssZZ', locale: str = 'en-us') -> str`
  - `Arrow.humanize(self, other: Union[ForwardRef('Arrow'), datetime.datetime, NoneType] = None, locale: str = 'en-us', only_distance: bool = False, granularity: Union[Literal['auto', 'second', 'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'], List[Literal['auto', 'second', 'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year']]] = 'auto') -> str`
  - `Arrow.month` attribute must exist on instances
  - `Arrow.year` attribute must exist on instances
- `get(*args: Any, **kwargs: Any) -> Arrow`

## Required Behavior

- The extracted feature must support this observable behavior: parse ISO and format-string datetimes. Required observable cases include get iso datetime; get with format string; parse lowercase month.
- The extracted feature must support this observable behavior: format with token literals in brackets. Required observable cases include format basic tokens; format literal brackets.
- The extracted feature must support this observable behavior: humanize relative deltas in English. Required observable cases include humanize relative hours; humanize past tense.
- The extracted feature must support this observable behavior: ordinal Do token parsing. Required observable cases include parse ordinal day token.
- The package exposes the required task API paths `featurelifted.Arrow`, `featurelifted.Arrow.day`, `featurelifted.Arrow.format`, `featurelifted.Arrow.humanize`, `featurelifted.Arrow.month`, `featurelifted.Arrow.year`, `featurelifted.get` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `arrow`.
- Do not implement 60+ locale packs beyond English.
- Do not implement timezone name database beyond utc/fixed offsets.
- Do not implement factory range/span utilities and CLI.
- Do not implement original arrow import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse ISO and format-string datetimes. Required observable cases include get iso datetime; get with format string; parse lowercase month.
- **B002** — The extracted feature must support this observable behavior: format with token literals in brackets. Required observable cases include format basic tokens; format literal brackets.
- **B003** — The extracted feature must support this observable behavior: humanize relative deltas in English. Required observable cases include humanize relative hours; humanize past tense.
- **B004** — The extracted feature must support this observable behavior: ordinal Do token parsing. Required observable cases include parse ordinal day token.
- **B005** — The package exposes the required task API paths `featurelifted.Arrow`, `featurelifted.Arrow.day`, `featurelifted.Arrow.format`, `featurelifted.Arrow.humanize`, `featurelifted.Arrow.month`, `featurelifted.Arrow.year`, `featurelifted.get` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: arrow.
<!-- featureliftbench:behavior-clauses:end -->
