# FeatureLift Task: pytest fixture name resolution

Extract a task-scoped subset of `pytest` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    deduplicate_names,
    fixture,
    FixtureDef,
    FixtureLookupError,
    FixtureRegistry,
    getfixturemarker,
    resolve_fixture_closure,
)
```

## Required API Details

- `FixtureDef(argname: 'str', argnames: 'tuple[str, ...]', baseid: 'str', scope: 'str' = 'function') -> None` class constructor
- `FixtureLookupError` must be importable and raisable
- `FixtureRegistry() -> 'None'` class constructor
  - `FixtureRegistry.register(self, fixturedef: 'FixtureDef') -> 'None'`
- `deduplicate_names(*seqs: 'Iterable[str]') -> 'tuple[str, ...]'`
- `fixture(fixture_function: 'FixtureFunction | None' = None, *, scope: 'str' = 'function', name: 'str | None' = None) -> 'FixtureFunctionMarker | FixtureFunction'`
- `getfixturemarker(obj: 'object') -> 'FixtureFunctionMarker | None'`
- `resolve_fixture_closure(parent_nodeids: 'AbstractSet[str]', initialnames: 'tuple[str, ...]', registry: 'FixtureRegistry', ignore_args: 'AbstractSet[str] | None' = None) -> 'tuple[list[str], dict[str, tuple[FixtureDef, ...]]]'`

## Required Behavior

- The extracted feature must support this observable behavior: resolve transitive fixture name closure from initial argnames. Required observable cases include resolve closure adds fixture dependencies; fixture lookup error lists available.
- The extracted feature must support this observable behavior: match fixture definitions to parent nodeids. Required observable cases include fixture lookup error lists available.
- The extracted feature must support this observable behavior: deduplicate fixture name sequences preserving order. Required observable cases include deduplicate names keeps first occurrence order.
- The extracted feature must support this observable behavior: sort closure fixtures by scope (session before function). Required observable cases include resolve closure adds fixture dependencies; getfixturemarker on decorated function; closure sorted by scope descending.
- The extracted feature must support this observable behavior: detect missing fixtures via FixtureLookupError. Required observable cases include getfixturemarker on decorated function; fixture lookup error lists available.
- The package exposes the required task API paths `featurelifted.FixtureDef`, `featurelifted.FixtureLookupError`, `featurelifted.FixtureRegistry`, `featurelifted.FixtureRegistry.register`, `featurelifted.deduplicate_names`, `featurelifted.fixture`, `featurelifted.getfixturemarker`, `featurelifted.resolve_fixture_closure` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pytest, _pytest`.
- Do not implement fixture execution, setup/teardown, and parametrization.
- Do not implement full pytest collection and plugin manager integration.
- Do not implement request.getfixturevalue dynamic lookup.
- Do not implement CLI, original tests, docs, packaging metadata.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: resolve transitive fixture name closure from initial argnames. Required observable cases include resolve closure adds fixture dependencies; fixture lookup error lists available.
- **B002** — The extracted feature must support this observable behavior: match fixture definitions to parent nodeids. Required observable cases include fixture lookup error lists available.
- **B003** — The extracted feature must support this observable behavior: deduplicate fixture name sequences preserving order. Required observable cases include deduplicate names keeps first occurrence order.
- **B004** — The extracted feature must support this observable behavior: sort closure fixtures by scope (session before function). Required observable cases include resolve closure adds fixture dependencies; getfixturemarker on decorated function; closure sorted by scope descending.
- **B005** — The extracted feature must support this observable behavior: detect missing fixtures via FixtureLookupError. Required observable cases include getfixturemarker on decorated function; fixture lookup error lists available.
- **B006** — The package exposes the required task API paths `featurelifted.FixtureDef`, `featurelifted.FixtureLookupError`, `featurelifted.FixtureRegistry`, `featurelifted.FixtureRegistry.register`, `featurelifted.deduplicate_names`, `featurelifted.fixture`, `featurelifted.getfixturemarker`, `featurelifted.resolve_fixture_closure` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pytest, _pytest.
<!-- featureliftbench:behavior-clauses:end -->
