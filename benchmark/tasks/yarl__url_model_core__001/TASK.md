# FeatureLift Task: URL parse, join, query, and path model

Extract a task-scoped subset of `yarl` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    cache_clear,
    cache_configure,
    cache_info,
    Query,
    QueryVariable,
    SimpleQuery,
    URL,
)
```

## Required API Details

- `URL` constant must exist
- `Query` object must exist
- `QueryVariable` object must exist
- `SimpleQuery` object must exist
- `cache_clear() -> None`
- `cache_configure(*, idna_encode_size: int | None = 256, idna_decode_size: int | None = 256, ip_address_size: int | None | UndefinedType = <UndefinedType._singleton: 0>, host_validate_size: int | None | UndefinedType = <UndefinedType._singleton: 0>, encode_host_size: int | None | UndefinedType = <UndefinedType._singleton: 0>) -> None`
- `cache_info() -> CacheInfo`

## Required Behavior

- The extracted feature must support this observable behavior: parse and construct URL objects with scheme, host, port, path, query, fragment. Required observable cases include basic parse components; with query kwargs; query no double unquote.
- The extracted feature must support this observable behavior: join absolute and relative URLs preserving query and fragment rules. Required observable cases include join absolute path; with query kwargs; join relative parent path; query no double unquote; join preserves base query when relative has query only; join rejects non url type.
- The extracted feature must support this observable behavior: MultiDict query with duplicate keys, ordering, and semicolon-in-value handling. Required observable cases include duplicate query keys multidict; semicolon in query value not separator; update query with multidict.
- The extracted feature must support this observable behavior: path normalization for dot and dot-dot segments. Required observable cases include joinpath appends segments; joinpath normalizes dot segments.
- The extracted feature must support this observable behavior: IDNA host encoding and decoding; default port omission in string form. Required observable cases include idna unicode host decoded; default http port omitted from str.
- The extracted feature must support this observable behavior: with_query, update_query, and joinpath helpers. Required observable cases include joinpath appends segments; joinpath normalizes dot segments; update query with multidict.
- The package exposes the required task API paths `featurelifted.URL`, `featurelifted.Query`, `featurelifted.QueryVariable`, `featurelifted.SimpleQuery`, `featurelifted.cache_clear`, `featurelifted.cache_configure`, `featurelifted.cache_info` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `yarl, aiohttp`.
- Do not implement aiohttp, network I/O, HTTP client/server integration.
- Do not implement Cython _quoting_c extension build (pure-Python quoting fallback only).
- Do not implement upstream test suite, docs, CI, and packaging metadata at runtime.
- Do not implement original yarl package import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse and construct URL objects with scheme, host, port, path, query, fragment. Required observable cases include basic parse components; with query kwargs; query no double unquote.
- **B002** — The extracted feature must support this observable behavior: join absolute and relative URLs preserving query and fragment rules. Required observable cases include join absolute path; with query kwargs; join relative parent path; query no double unquote; join preserves base query when relative has query only; join rejects non url type.
- **B003** — The extracted feature must support this observable behavior: MultiDict query with duplicate keys, ordering, and semicolon-in-value handling. Required observable cases include duplicate query keys multidict; semicolon in query value not separator; update query with multidict.
- **B004** — The extracted feature must support this observable behavior: path normalization for dot and dot-dot segments. Required observable cases include joinpath appends segments; joinpath normalizes dot segments.
- **B005** — The extracted feature must support this observable behavior: IDNA host encoding and decoding; default port omission in string form. Required observable cases include idna unicode host decoded; default http port omitted from str.
- **B006** — The extracted feature must support this observable behavior: with_query, update_query, and joinpath helpers. Required observable cases include joinpath appends segments; joinpath normalizes dot segments; update query with multidict.
- **B007** — The package exposes the required task API paths `featurelifted.URL`, `featurelifted.Query`, `featurelifted.QueryVariable`, `featurelifted.SimpleQuery`, `featurelifted.cache_clear`, `featurelifted.cache_configure`, `featurelifted.cache_info` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: yarl, aiohttp.
<!-- featureliftbench:behavior-clauses:end -->
