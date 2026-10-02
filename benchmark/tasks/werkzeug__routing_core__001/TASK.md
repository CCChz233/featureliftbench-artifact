# FeatureLift Task: URL routing map and adapter

Extract a task-scoped subset of `werkzeug` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    routing,
)
```

## Required API Details

- `routing` module must be importable
  - `routing.Map(rules: 't.Iterable[RuleFactory] | None' = None, default_subdomain: 'str' = '', strict_slashes: 'bool' = True, merge_slashes: 'bool' = True, redirect_defaults: 'bool' = True, converters: 't.Mapping[str, type[BaseConverter]] | None' = None, sort_parameters: 'bool' = False, sort_key: 't.Callable[[t.Any], t.Any] | None' = None, host_matching: 'bool' = False) -> 'None'` class constructor
    - `routing.Map.bind(self, server_name: 'str', script_name: 'str | None' = None, subdomain: 'str | None' = None, url_scheme: 'str' = 'http', default_method: 'str' = 'GET', path_info: 'str | None' = None, query_args: 't.Mapping[str, t.Any] | str | None' = None) -> 'MapAdapter'`
  - `routing.Rule(string: 'str', defaults: 't.Mapping[str, t.Any] | None' = None, subdomain: 'str | None' = None, methods: 't.Iterable[str] | None' = None, build_only: 'bool' = False, endpoint: 't.Any | None' = None, strict_slashes: 'bool | None' = None, merge_slashes: 'bool | None' = None, redirect_to: 'str | t.Callable[..., str] | None' = None, alias: 'bool' = False, host: 'str | None' = None, websocket: 'bool' = False) -> 'None'` class constructor
  - `routing.Subdomain(subdomain: 'str', rules: 't.Iterable[RuleFactory]') -> 'None'` class constructor
  - `routing.Submount(path: 'str', rules: 't.Iterable[RuleFactory]') -> 'None'` class constructor
- `routing.exceptions` module must be importable
  - `routing.exceptions.RequestRedirect` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: define URL rules with converters and HTTP methods. Required observable cases include subdomain and submount routing.
- The extracted feature must support this observable behavior: match paths to endpoints with argument extraction. Required observable cases include match and build simple rules; subdomain and submount routing.
- The extracted feature must support this observable behavior: build URLs from endpoints and arguments. Required observable cases include match and build simple rules; subdomain and submount routing.
- The extracted feature must support this observable behavior: subdomain and submount rule factories. Required observable cases include subdomain and submount routing.
- The extracted feature must support this observable behavior: redirect and alias redirect exceptions on match. Required observable cases include strict slashes redirect.
- The package exposes the required task API paths `featurelifted.routing`, `featurelifted.routing.Map`, `featurelifted.routing.Map.bind`, `featurelifted.routing.Rule`, `featurelifted.routing.Subdomain`, `featurelifted.routing.Submount`, `featurelifted.routing.exceptions`, `featurelifted.routing.exceptions.RequestRedirect` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `werkzeug`.
- Do not implement WSGI request/response wrappers.
- Do not implement development server and middleware.
- Do not implement form parsing and file uploads.
- Do not implement original project tests and CLI.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: define URL rules with converters and HTTP methods. Required observable cases include subdomain and submount routing.
- **B002** — The extracted feature must support this observable behavior: match paths to endpoints with argument extraction. Required observable cases include match and build simple rules; subdomain and submount routing.
- **B003** — The extracted feature must support this observable behavior: build URLs from endpoints and arguments. Required observable cases include match and build simple rules; subdomain and submount routing.
- **B004** — The extracted feature must support this observable behavior: subdomain and submount rule factories. Required observable cases include subdomain and submount routing.
- **B005** — The extracted feature must support this observable behavior: redirect and alias redirect exceptions on match. Required observable cases include strict slashes redirect.
- **B006** — The package exposes the required task API paths `featurelifted.routing`, `featurelifted.routing.Map`, `featurelifted.routing.Map.bind`, `featurelifted.routing.Rule`, `featurelifted.routing.Subdomain`, `featurelifted.routing.Submount`, `featurelifted.routing.exceptions`, `featurelifted.routing.exceptions.RequestRedirect` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: werkzeug.
<!-- featureliftbench:behavior-clauses:end -->
