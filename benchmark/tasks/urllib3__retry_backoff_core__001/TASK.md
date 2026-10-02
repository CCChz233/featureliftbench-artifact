# FeatureLift Task: Retry backoff policy core

Extract a task-scoped subset of `urllib3` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ConnectTimeoutError,
    InvalidHeader,
    MaxRetryError,
    ReadTimeoutError,
    RequestHistory,
    ResponseError,
    Retry,
)
```

## Required API Details

- `Retry(total: 'bool | int | None' = 10, connect: 'int | None' = None, read: 'int | None' = None, redirect: 'bool | int | None' = None, status: 'int | None' = None, other: 'int | None' = None, allowed_methods: 'typing.Collection[str] | None' = frozenset({'GET', 'DELETE', 'PUT', 'HEAD', 'TRACE', 'OPTIONS'}), status_forcelist: 'typing.Collection[int] | None' = None, backoff_factor: 'float' = 0, backoff_max: 'float' = 120, raise_on_redirect: 'bool' = True, raise_on_status: 'bool' = True, history: 'tuple[RequestHistory, ...] | None' = None, respect_retry_after_header: 'bool' = True, remove_headers_on_redirect: 'typing.Collection[str]' = frozenset({'Proxy-Authorization', 'Authorization', 'Cookie'}), backoff_jitter: 'float' = 0.0) -> 'None'` class constructor
  - `Retry.get_backoff_time(self) -> 'float'`
  - `Retry.history` attribute must exist on instances
  - `Retry.increment(self, method: 'str | None' = None, url: 'str | None' = None, response: 'BaseHTTPResponse | None' = None, error: 'Exception | None' = None, _pool: 'ConnectionPool | None' = None, _stacktrace: 'TracebackType | None' = None) -> 'Self'`
  - `Retry.is_retry(self, method: 'str', status_code: 'int', has_retry_after: 'bool' = False) -> 'bool'`
  - `Retry.parse_retry_after(self, retry_after: 'str') -> 'float'`
  - `Retry.remove_headers_on_redirect` attribute must exist on instances
  - `Retry.from_int(retries: 'Retry | bool | int | None', redirect: 'bool | int | None' = True, default: 'Retry | bool | int | None' = None) -> 'Retry'`
  - `Retry.total` attribute must exist on instances
- `RequestHistory(method: ForwardRef('str | None'), url: ForwardRef('str | None'), error: ForwardRef('Exception | None'), status: ForwardRef('int | None'), redirect_location: ForwardRef('str | None'))` class constructor
- `ConnectTimeoutError` must be importable and raisable
- `ReadTimeoutError` must be importable and raisable
- `MaxRetryError` must be importable and raisable
- `ResponseError` must be importable and raisable
  - `ResponseError.SPECIFIC_ERROR` attribute must exist
- `InvalidHeader` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: Retry defaults and from_int coercion. Required observable cases include retry defaults and from int; total wins over connect.
- The extracted feature must support this observable behavior: connect/read/status/redirect/other counter decrement and exhaustion. Required observable cases include connect timeout increment; total wins over connect.
- The extracted feature must support this observable behavior: status_forcelist and allowed_methods conjunction. Required observable cases include is retry status forcelist; allowed methods and status forcelist and; read timeout requires allowed method; status increment raises specific error.
- The extracted feature must support this observable behavior: exponential backoff with max cap and redirect reset. Required observable cases include backoff progression; backoff resets after redirect.
- The extracted feature must support this observable behavior: Retry-After header parsing with numeric and HTTP-date forms. Required observable cases include parse retry after numeric and invalid.
- The extracted feature must support this observable behavior: RequestHistory accumulation on increment. Required observable cases include connect timeout increment; history accumulates; status increment raises specific error.
- The extracted feature must support this observable behavior: remove_headers_on_redirect lowercasing. Required observable cases include remove headers on redirect lowercased.
- The package exposes the required task API paths `featurelifted.Retry`, `featurelifted.Retry.get_backoff_time`, `featurelifted.Retry.history`, `featurelifted.Retry.increment`, `featurelifted.Retry.is_retry`, `featurelifted.Retry.parse_retry_after`, `featurelifted.Retry.remove_headers_on_redirect`, `featurelifted.Retry.from_int`, `featurelifted.Retry.total`, `featurelifted.RequestHistory`, `featurelifted.ConnectTimeoutError`, `featurelifted.ReadTimeoutError`, and 4 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `urllib3`.
- Do not implement HTTP connection pools, sockets, TLS, and actual request/response I/O.
- Do not implement PoolManager and connectionpool integration.
- Do not implement upstream test suite and dummyserver.
- Do not implement original urllib3 import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: Retry defaults and from_int coercion. Required observable cases include retry defaults and from int; total wins over connect.
- **B002** — The extracted feature must support this observable behavior: connect/read/status/redirect/other counter decrement and exhaustion. Required observable cases include connect timeout increment; total wins over connect.
- **B003** — The extracted feature must support this observable behavior: status_forcelist and allowed_methods conjunction. Required observable cases include is retry status forcelist; allowed methods and status forcelist and; read timeout requires allowed method; status increment raises specific error.
- **B004** — The extracted feature must support this observable behavior: exponential backoff with max cap and redirect reset. Required observable cases include backoff progression; backoff resets after redirect.
- **B005** — The extracted feature must support this observable behavior: Retry-After header parsing with numeric and HTTP-date forms. Required observable cases include parse retry after numeric and invalid.
- **B006** — The extracted feature must support this observable behavior: RequestHistory accumulation on increment. Required observable cases include connect timeout increment; history accumulates; status increment raises specific error.
- **B007** — The extracted feature must support this observable behavior: remove_headers_on_redirect lowercasing. Required observable cases include remove headers on redirect lowercased.
- **B008** — The package exposes the required task API paths `featurelifted.Retry`, `featurelifted.Retry.get_backoff_time`, `featurelifted.Retry.history`, `featurelifted.Retry.increment`, `featurelifted.Retry.is_retry`, `featurelifted.Retry.parse_retry_after`, `featurelifted.Retry.remove_headers_on_redirect`, `featurelifted.Retry.from_int`, `featurelifted.Retry.total`, `featurelifted.RequestHistory`, `featurelifted.ConnectTimeoutError`, `featurelifted.ReadTimeoutError`, and 4 listed members with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: urllib3.
<!-- featureliftbench:behavior-clauses:end -->
