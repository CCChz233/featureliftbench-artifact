# FeatureLift Task: HTTP request model and offline request builder

Extract a task-scoped subset of `httpx` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    build_request,
    Cookies,
    Headers,
    InvalidURL,
    QueryParams,
    Request,
    URL,
)
```

## Required API Details

- `URL` constant must exist
- `QueryParams(*args: 'QueryParamTypes | None', **kwargs: 'typing.Any') -> 'None'` class constructor
  - `QueryParams.multi_items(self) -> 'list[tuple[str, str]]'`
  - `QueryParams.merge(self, params: 'QueryParamTypes | None' = None) -> 'QueryParams'`
- `Headers(headers: 'HeaderTypes | None' = None, encoding: 'str | None' = None) -> 'None'` class constructor
  - `Headers.raw` attribute must exist on instances
- `Cookies(cookies: 'CookieTypes | None' = None) -> 'None'` class constructor
- `Request(method: 'str | bytes', url: 'URL | str', *, params: 'QueryParamTypes | None' = None, headers: 'HeaderTypes | None' = None, cookies: 'CookieTypes | None' = None, content: 'RequestContent | None' = None, data: 'RequestData | None' = None, files: 'RequestFiles | None' = None, json: 'typing.Any | None' = None, stream: 'SyncByteStream | AsyncByteStream | None' = None, extensions: 'RequestExtensions | None' = None) -> 'None'` class constructor
  - `Request.content` attribute must exist on instances
  - `Request.headers` attribute must exist on instances
  - `Request.url` attribute must exist on instances
- `build_request(method: 'str', url: 'URLTypes', *, base_url: 'str | URL' = '', params: 'QueryParamTypes | None' = None, headers: 'HeaderTypes | None' = None, cookies: 'CookieTypes | None' = None, default_params: 'QueryParamTypes | None' = None, default_headers: 'HeaderTypes | None' = None, default_cookies: 'CookieTypes | None' = None, content: 'typing.Any' = None, data: 'typing.Any' = None, json: 'typing.Any' = None, files: 'typing.Any' = None) -> 'Request'`
- `InvalidURL` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: construct and join URL objects with base URL and query parameters. Required observable cases include url path and query; base url join and duplicate query params; url idna and percent encoding.
- The extracted feature must support this observable behavior: preserve query parameter ordering and duplicate keys in QueryParams. Required observable cases include query params from mapping; query params duplicate and empty value.
- The extracted feature must support this observable behavior: case-insensitive header lookup with raw header preservation. Required observable cases include headers case insensitive lookup; url idna and percent encoding.
- The extracted feature must support this observable behavior: merge default and per-request headers, query params, and cookies. Required observable cases include query params from mapping; cookies simple header; build request merges defaults; headers cookie merge and request object; build request merges client defaults; query params duplicate and empty value.
- The extracted feature must support this observable behavior: build Request objects with content, data, and json body helpers. Required observable cases include build request merges defaults; request content data json headers.
- The extracted feature must support this observable behavior: raise compatible errors for invalid URL and request input. Required observable cases include url idna and percent encoding; invalid url raises.
- The package exposes the required task API paths `featurelifted.URL`, `featurelifted.QueryParams`, `featurelifted.QueryParams.multi_items`, `featurelifted.QueryParams.merge`, `featurelifted.Headers`, `featurelifted.Headers.raw`, `featurelifted.Cookies`, `featurelifted.Request`, `featurelifted.Request.content`, `featurelifted.Request.headers`, `featurelifted.Request.url`, `featurelifted.build_request`, and 1 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `httpx`.
- Do not implement network I/O, transports, connection pools, proxies, redirects.
- Do not implement Client.send, AsyncClient, response parsing and streaming.
- Do not implement authentication flows beyond request header construction.
- Do not implement original httpx package import at runtime.
- Do not implement CLI, docs, CI, and original tests.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: construct and join URL objects with base URL and query parameters. Required observable cases include url path and query; base url join and duplicate query params; url idna and percent encoding.
- **B002** — The extracted feature must support this observable behavior: preserve query parameter ordering and duplicate keys in QueryParams. Required observable cases include query params from mapping; query params duplicate and empty value.
- **B003** — The extracted feature must support this observable behavior: case-insensitive header lookup with raw header preservation. Required observable cases include headers case insensitive lookup; url idna and percent encoding.
- **B004** — The extracted feature must support this observable behavior: merge default and per-request headers, query params, and cookies. Required observable cases include query params from mapping; cookies simple header; build request merges defaults; headers cookie merge and request object; build request merges client defaults; query params duplicate and empty value.
- **B005** — The extracted feature must support this observable behavior: build Request objects with content, data, and json body helpers. Required observable cases include build request merges defaults; request content data json headers.
- **B006** — The extracted feature must support this observable behavior: raise compatible errors for invalid URL and request input. Required observable cases include url idna and percent encoding; invalid url raises.
- **B007** — The package exposes the required task API paths `featurelifted.URL`, `featurelifted.QueryParams`, `featurelifted.QueryParams.multi_items`, `featurelifted.QueryParams.merge`, `featurelifted.Headers`, `featurelifted.Headers.raw`, `featurelifted.Cookies`, `featurelifted.Request`, `featurelifted.Request.content`, `featurelifted.Request.headers`, `featurelifted.Request.url`, `featurelifted.build_request`, and 1 listed members with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: httpx.
<!-- featureliftbench:behavior-clauses:end -->
