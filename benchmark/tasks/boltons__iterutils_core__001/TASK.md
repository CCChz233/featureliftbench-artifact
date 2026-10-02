# FeatureLift Task: Iterutils iterator toolkit

Extract a task-scoped subset of `boltons` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    bucketize,
    chunked,
    get_path,
    iterutils,
    pairwise,
    partition,
    remap,
    unique,
    windowed,
)
```

## Required API Details

- `chunked(src, size, count=None, **kw)`
- `windowed(src, size)`
- `pairwise(src)`
- `unique(src, key=None)`
- `bucketize(src, key=<class 'bool'>, value_transform=None, key_filter=None)`
- `remap(root, visit=<function default_visit>, enter=<function default_enter>, exit=<function default_exit>, **kwargs)`
- `get_path(root, path, default=<object object>)`
- `partition(src, key=<class 'bool'>)`
- `iterutils` module must be importable
  - `iterutils.backoff(start, stop, count=None, factor=2.0, jitter=False)`
  - `iterutils.chunk_ranges(input_size, chunk_size, input_offset=0, overlap_size=0, align=False)`

## Required Behavior

- The extracted feature must support this observable behavior: chunked and windowed iteration with size validation. Required observable cases include chunked basic; windowed and pairwise; chunked fill padding; chunked count limit; pairwise sliding window; windowed size three.
- The extracted feature must support this observable behavior: pairwise adjacent pairs. Required observable cases include windowed and pairwise; pairwise sliding window.
- The extracted feature must support this observable behavior: unique with optional key function. Required observable cases include unique and bucketize; unique key preserves first of length.
- The extracted feature must support this observable behavior: bucketize grouping with key_filter and value_transform. Required observable cases include unique and bucketize; bucketize value transform.
- The extracted feature must support this observable behavior: remap tree walk with visit/enter/exit hooks. Required observable cases include windowed size three.
- The extracted feature must support this observable behavior: get_path nested dict/list access. Required observable cases include get path missing raises.
- The package exposes the required task API paths `featurelifted.chunked`, `featurelifted.windowed`, `featurelifted.pairwise`, `featurelifted.unique`, `featurelifted.bucketize`, `featurelifted.remap`, `featurelifted.get_path`, `featurelifted.partition`, `featurelifted.iterutils`, `featurelifted.iterutils.backoff`, `featurelifted.iterutils.chunk_ranges` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `boltons`.
- Do not implement other boltons utility modules beyond curated snapshot.
- Do not implement upstream docs and packaging.
- Do not implement original boltons import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: chunked and windowed iteration with size validation. Required observable cases include chunked basic; windowed and pairwise; chunked fill padding; chunked count limit; pairwise sliding window; windowed size three.
- **B002** — The extracted feature must support this observable behavior: pairwise adjacent pairs. Required observable cases include windowed and pairwise; pairwise sliding window.
- **B003** — The extracted feature must support this observable behavior: unique with optional key function. Required observable cases include unique and bucketize; unique key preserves first of length.
- **B004** — The extracted feature must support this observable behavior: bucketize grouping with key_filter and value_transform. Required observable cases include unique and bucketize; bucketize value transform.
- **B005** — The extracted feature must support this observable behavior: remap tree walk with visit/enter/exit hooks. Required observable cases include windowed size three.
- **B006** — The extracted feature must support this observable behavior: get_path nested dict/list access. Required observable cases include get path missing raises.
- **B007** — The package exposes the required task API paths `featurelifted.chunked`, `featurelifted.windowed`, `featurelifted.pairwise`, `featurelifted.unique`, `featurelifted.bucketize`, `featurelifted.remap`, `featurelifted.get_path`, `featurelifted.partition`, `featurelifted.iterutils`, `featurelifted.iterutils.backoff`, `featurelifted.iterutils.chunk_ranges` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: boltons.
<!-- featureliftbench:behavior-clauses:end -->
