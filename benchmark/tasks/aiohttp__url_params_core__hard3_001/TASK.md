# FeatureLift Task: build_url normalize_headers

Extract a task-scoped subset of `aiohttp` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    build_url,
    CIMultiDict,
    InvalidHeaderName,
    normalize_headers,
)
```

## Required API Details

- `build_url(base: 'str', params: 'list[tuple[str, str]]') -> 'str'`
- `normalize_headers(headers: 'dict[str, str]') -> 'CIMultiDict'`
- `CIMultiDict(*args, **kwargs) -> 'None'` class constructor
  - `CIMultiDict.getall(self, key: 'str') -> 'list[str]'`
  - `CIMultiDict.__getitem__(self, key: 'str') -> 'str'`
  - `CIMultiDict.__setitem__(self, key: 'str', value: 'str') -> 'None'`
- `InvalidHeaderName` must be importable and raisable

## Required Behavior

- `build_url` merges query parameters into a base URL.
- `normalize_headers` returns a case-insensitive `CIMultiDict`.
- Invalid header names raise `InvalidHeaderName`.
- The package exposes the required task API paths `featurelifted.build_url`, `featurelifted.normalize_headers`, `featurelifted.CIMultiDict`, `featurelifted.CIMultiDict.getall`, `featurelifted.CIMultiDict.__getitem__`, `featurelifted.CIMultiDict.__setitem__`, `featurelifted.InvalidHeaderName` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `aiohttp`.
- Forbidden path access: `repo/, aiohttp/`.
- Do not implement network access.
- Do not implement client/server runtime.
- Do not implement async I/O.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `build_url` merges query parameters into a base URL.
- **B002** — `normalize_headers` returns a case-insensitive `CIMultiDict`.
- **B003** — Invalid header names raise `InvalidHeaderName`.
- **B004** — The package exposes the required task API paths `featurelifted.build_url`, `featurelifted.normalize_headers`, `featurelifted.CIMultiDict`, `featurelifted.CIMultiDict.getall`, `featurelifted.CIMultiDict.__getitem__`, `featurelifted.CIMultiDict.__setitem__`, `featurelifted.InvalidHeaderName` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: aiohttp.
<!-- featureliftbench:behavior-clauses:end -->
