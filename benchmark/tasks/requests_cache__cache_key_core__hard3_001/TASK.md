# FeatureLift Task: HTTP request cache key and expiration policy

Extract a task-scoped subset of `requests_cache` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CachePolicy,
    create_cache_key,
    create_key,
    get_expiration,
    normalize_body,
    normalize_headers,
    normalize_params,
)
```

## Required API Details

- `CachePolicy(should_store: 'bool', expiration_seconds: 'int | None', reason: 'str' = '') -> None` class constructor
  - `CachePolicy.from_headers(headers: 'dict[str, Any] | None', default: 'int | None' = None, now: 'datetime | None' = None) -> "'CachePolicy'"`
  - `CachePolicy.expiration_seconds` attribute must exist on instances
  - `CachePolicy.should_store` attribute must exist on instances
- `create_key(method: 'str', url: 'str', params=None, headers: 'dict[str, Any] | None' = None, body: 'Any' = None, ignored_parameters=None, match_headers: 'bool | list[str] | tuple[str, ...]' = False, verify: 'bool' = True, serializer: 'Any' = None, content_root_key: 'str | None' = None) -> 'str'`
- `get_expiration(headers: 'dict[str, Any] | None', default: 'int | None' = None, now: 'datetime | None' = None) -> 'int | None'`
- `create_cache_key(request: 'Any', **kwargs: 'Any') -> 'str'`
- `normalize_body(body: 'Any', headers: 'dict[str, Any] | None' = None, ignored_parameters=None, content_root_key: 'str | None' = None) -> 'bytes'`
- `normalize_headers(headers: 'dict[str, Any] | None', ignored_parameters=None) -> 'dict[str, str]'`
- `normalize_params(value: 'Any', ignored_parameters=None) -> 'str'`

## Required Behavior

- create_key normalizes method, URL, parameters, selected headers, and body before returning a deterministic cache-key digest.
- create_cache_key reads request-like objects and produces the same key as create_key with equivalent explicit fields.
- normalize_url lowercases scheme and host, merges explicit parameters, sorts query items, and preserves key-only or repeated parameters.
- normalize_params sorts parameters and redacts configured ignored values without removing their keys.
- normalize_headers includes only matched headers, normalizes names and whitespace, and deterministically orders multi-value content.
- normalize_body canonicalizes JSON key order and form-encoded parameters and redacts ignored values in both body forms.
- get_matched_headers returns the normalized header subset requested by match_headers and excludes unmatched headers.
- CachePolicy.from_headers interprets Cache-Control and Expires headers into storage and expiration decisions.
- get_expiration returns max-age seconds, Expires relative to now, no-store suppression, or the declared default when no directive applies.
- `Cache-Control: max-age=N` sets expiration to `N` seconds.
- Use `default` expiration when no cache header applies.
- The package exposes the required task API paths `featurelifted.CachePolicy`, `featurelifted.CachePolicy.from_headers`, `featurelifted.CachePolicy.expiration_seconds`, `featurelifted.CachePolicy.should_store`, `featurelifted.create_key`, `featurelifted.get_expiration`, `featurelifted.create_cache_key`, `featurelifted.normalize_body`, `featurelifted.normalize_headers`, `featurelifted.normalize_params` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `requests_cache, requests, url_normalize`.
- Forbidden path access: `repo/, requests_cache/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement HTTP sessions.
- Do not implement cache backends.
- Do not implement serializers.
- Do not implement Redis/MongoDB/SQLite/filesystem storage.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — create_key normalizes method, URL, parameters, selected headers, and body before returning a deterministic cache-key digest.
- **B002** — create_cache_key reads request-like objects and produces the same key as create_key with equivalent explicit fields.
- **B003** — normalize_url lowercases scheme and host, merges explicit parameters, sorts query items, and preserves key-only or repeated parameters.
- **B004** — normalize_params sorts parameters and redacts configured ignored values without removing their keys.
- **B005** — normalize_headers includes only matched headers, normalizes names and whitespace, and deterministically orders multi-value content.
- **B006** — normalize_body canonicalizes JSON key order and form-encoded parameters and redacts ignored values in both body forms.
- **B007** — get_matched_headers returns the normalized header subset requested by match_headers and excludes unmatched headers.
- **B008** — CachePolicy.from_headers interprets Cache-Control and Expires headers into storage and expiration decisions.
- **B009** — get_expiration returns max-age seconds, Expires relative to now, no-store suppression, or the declared default when no directive applies.
- **B010** — `Cache-Control: max-age=N` sets expiration to `N` seconds.
- **B011** — Use `default` expiration when no cache header applies.
- **B012** — The package exposes the required task API paths `featurelifted.CachePolicy`, `featurelifted.CachePolicy.from_headers`, `featurelifted.CachePolicy.expiration_seconds`, `featurelifted.CachePolicy.should_store`, `featurelifted.create_key`, `featurelifted.get_expiration`, `featurelifted.create_cache_key`, `featurelifted.normalize_body`, `featurelifted.normalize_headers`, `featurelifted.normalize_params` with the kinds and callable signatures listed in this contract.
- **B013** — the submitted package does not import forbidden upstream packages: requests_cache, requests, url_normalize.
<!-- featureliftbench:behavior-clauses:end -->
