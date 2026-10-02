# FeatureLift Task: RFC3986 URI parse, build, and validate subset

Extract a task-scoped subset of `rfc3986` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    is_valid_uri,
    normalize_uri,
    uri_reference,
    URIBuilder,
    URIReference,
)
```

## Required API Details

- `URIBuilder(scheme=None, userinfo=None, host=None, port=None, path=None, query=None, fragment=None)` class constructor
  - `URIBuilder.from_uri(reference)`
  - `URIBuilder.add_scheme(self, scheme)`
  - `URIBuilder.add_host(self, host)`
  - `URIBuilder.add_path(self, path)`
  - `URIBuilder.finalize(self)`
- `URIReference(scheme, authority, path, query, fragment, encoding='utf-8')` class constructor
- `is_valid_uri(uri, encoding='utf-8', **kwargs)`
- `normalize_uri(uri, encoding='utf-8')`
- `uri_reference(uri, encoding='utf-8')`

## Required Behavior

- The extracted feature must support this observable behavior: parse URI components and authority subcomponents. Required observable cases include uri reference components; authority userinfo host port; builder from uri roundtrip.
- The extracted feature must support this observable behavior: normalize scheme/host/path. Required observable cases include authority userinfo host port; normalize uri path dots; uri reference ipv6 host; normalize preserves fragment.
- The extracted feature must support this observable behavior: URIBuilder compose and finalize. Required observable cases include uri builder finalize; uri reference ipv6 host.
- The extracted feature must support this observable behavior: is_valid_uri convenience check. Required observable cases include is valid uri https; builder from uri roundtrip; uri reference ipv6 host.
- The package exposes the required task API paths `featurelifted.URIBuilder`, `featurelifted.URIBuilder.from_uri`, `featurelifted.URIBuilder.add_scheme`, `featurelifted.URIBuilder.add_host`, `featurelifted.URIBuilder.add_path`, `featurelifted.URIBuilder.finalize`, `featurelifted.URIReference`, `featurelifted.is_valid_uri`, `featurelifted.normalize_uri`, `featurelifted.uri_reference` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `rfc3986`.
- Do not implement IRI full unicode normalization.
- Do not implement validators beyond basic is_valid_uri.
- Do not implement original rfc3986 import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse URI components and authority subcomponents. Required observable cases include uri reference components; authority userinfo host port; builder from uri roundtrip.
- **B002** — The extracted feature must support this observable behavior: normalize scheme/host/path. Required observable cases include authority userinfo host port; normalize uri path dots; uri reference ipv6 host; normalize preserves fragment.
- **B003** — The extracted feature must support this observable behavior: URIBuilder compose and finalize. Required observable cases include uri builder finalize; uri reference ipv6 host.
- **B004** — The extracted feature must support this observable behavior: is_valid_uri convenience check. Required observable cases include is valid uri https; builder from uri roundtrip; uri reference ipv6 host.
- **B005** — The package exposes the required task API paths `featurelifted.URIBuilder`, `featurelifted.URIBuilder.from_uri`, `featurelifted.URIBuilder.add_scheme`, `featurelifted.URIBuilder.add_host`, `featurelifted.URIBuilder.add_path`, `featurelifted.URIBuilder.finalize`, `featurelifted.URIReference`, `featurelifted.is_valid_uri`, `featurelifted.normalize_uri`, `featurelifted.uri_reference` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: rfc3986.
<!-- featureliftbench:behavior-clauses:end -->
