# FeatureLift Task: Request matcher registry and call history

Extract a task-scoped subset of `responses` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    header_matcher,
    MockResponse,
    MockResponseRegistry,
    query_string_matcher,
)
```

## Required API Details

- `MockResponseRegistry() -> 'None'` class constructor
  - `MockResponseRegistry._responses` attribute must exist on instances
  - `MockResponseRegistry.add(self, response: 'MockResponse') -> 'MockResponse'`
  - `MockResponseRegistry.call_history` attribute must exist on instances
  - `MockResponseRegistry.find(self, request: 'PreparedRequest') -> 'tuple[MockResponse | None, list[str]]'`
  - `MockResponseRegistry.reset(self) -> 'None'`
- `MockResponse(url: 'str', method: 'str' = 'GET', status: 'int' = 200, body: 'Any' = '', match_querystring: 'bool' = False, headers: 'dict[str, str]' = <factory>, matchers: 'list[Callable[[PreparedRequest], tuple[bool, str]]]' = <factory>, call_count: 'int' = 0, once: 'bool' = False) -> None` class constructor
- `query_string_matcher(params: 'dict[str, str]') -> 'Callable[[PreparedRequest], tuple[bool, str]]'`
- `header_matcher(headers: 'dict[str, str]') -> 'Callable[[PreparedRequest], tuple[bool, str]]'`

## Required Behavior

- Register `MockResponse` objects and find the first matching `PreparedRequest`.
- Support `query_string_matcher` and `header_matcher` helper matchers.
- `once=True` responses are removed after the first successful match.
- `reset()` clears registered responses and call history.
- The package exposes the required task API paths `featurelifted.MockResponseRegistry`, `featurelifted.MockResponseRegistry._responses`, `featurelifted.MockResponseRegistry.add`, `featurelifted.MockResponseRegistry.call_history`, `featurelifted.MockResponseRegistry.find`, `featurelifted.MockResponseRegistry.reset`, `featurelifted.MockResponse`, `featurelifted.query_string_matcher`, `featurelifted.header_matcher` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `responses`.
- Forbidden path access: `repo/, responses/`.
- Do not implement network access.
- Do not implement socket patching.
- Do not implement HTTP adapter interception.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — Register `MockResponse` objects and find the first matching `PreparedRequest`.
- **B002** — Support `query_string_matcher` and `header_matcher` helper matchers.
- **B003** — `once=True` responses are removed after the first successful match.
- **B004** — `reset()` clears registered responses and call history.
- **B005** — The package exposes the required task API paths `featurelifted.MockResponseRegistry`, `featurelifted.MockResponseRegistry._responses`, `featurelifted.MockResponseRegistry.add`, `featurelifted.MockResponseRegistry.call_history`, `featurelifted.MockResponseRegistry.find`, `featurelifted.MockResponseRegistry.reset`, `featurelifted.MockResponse`, `featurelifted.query_string_matcher`, `featurelifted.header_matcher` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: responses.
<!-- featureliftbench:behavior-clauses:end -->
