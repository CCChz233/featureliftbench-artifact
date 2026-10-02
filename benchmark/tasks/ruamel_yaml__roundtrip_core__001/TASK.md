# FeatureLift Task: YAML roundtrip with comments

Extract a task-scoped subset of `ruamel` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CommentedMap,
    round_trip_dump,
    round_trip_load,
    YAML,
)
```

## Required API Details

- `YAML` constant must exist
- `round_trip_load(stream: 'StreamTextType', version: 'Optional[VersionType]' = None, preserve_quotes: 'Optional[bool]' = None) -> 'Any'`
- `round_trip_dump(data: 'Any', stream: 'Optional[StreamType]' = None, Dumper: 'Any' = <class 'RoundTripDumper'>, default_style: 'Any' = None, default_flow_style: 'Any' = None, canonical: 'Optional[bool]' = None, indent: 'Optional[int]' = None, width: 'Optional[int]' = None, allow_unicode: 'Optional[bool]' = None, line_break: 'Any' = None, encoding: 'Any' = None, explicit_start: 'Optional[bool]' = None, explicit_end: 'Optional[bool]' = None, version: 'Optional[VersionType]' = None, tags: 'Any' = None, block_seq_indent: 'Any' = None, top_level_colon_align: 'Any' = None, prefix_colon: 'Any' = None) -> 'Any'`
- `CommentedMap(*args: 'Any', **kw: 'Any') -> 'None'` class constructor
  - `CommentedMap.fa` attribute must exist on instances

## Required Behavior

- The extracted feature must support this observable behavior: round-trip load/dump preserves end-of-line comments. Required observable cases include roundtrip basic mapping; eol comment preserved; flow style dump; anchor alias roundtrip.
- The extracted feature must support this observable behavior: CommentedMap key order preserved. Required observable cases include key order preserved; no ruamel import surface.
- The extracted feature must support this observable behavior: flow style and literal block scalars. Required observable cases include flow style dump; literal block scalar.
- The package exposes the required task API paths `featurelifted.YAML`, `featurelifted.round_trip_load`, `featurelifted.round_trip_dump`, `featurelifted.CommentedMap`, `featurelifted.CommentedMap.fa` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `ruamel`.
- Do not implement C yaml acceleration.
- Do not implement jinja2 templating.
- Do not implement original ruamel import.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: round-trip load/dump preserves end-of-line comments. Required observable cases include roundtrip basic mapping; eol comment preserved; flow style dump; anchor alias roundtrip.
- **B002** — The extracted feature must support this observable behavior: CommentedMap key order preserved. Required observable cases include key order preserved; no ruamel import surface.
- **B003** — The extracted feature must support this observable behavior: flow style and literal block scalars. Required observable cases include flow style dump; literal block scalar.
- **B004** — The package exposes the required task API paths `featurelifted.YAML`, `featurelifted.round_trip_load`, `featurelifted.round_trip_dump`, `featurelifted.CommentedMap`, `featurelifted.CommentedMap.fa` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: ruamel.
<!-- featureliftbench:behavior-clauses:end -->
