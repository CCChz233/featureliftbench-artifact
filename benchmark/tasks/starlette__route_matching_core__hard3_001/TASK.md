# FeatureLift Task: Route matching and URL path convertor registry

Extract a task-scoped subset of `starlette` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    compile_path,
    Match,
    Mount,
    Route,
    Router,
)
```

## Required API Details

- `compile_path(path: 'str') -> 'tuple[Pattern[str], str, dict[str, Convertor]]'`
- `Route(name: 'str', path: 'str', methods: 'list[str]' = <factory>, endpoint: 'Callable[..., Any] | None' = None) -> None` class constructor
  - `Route.matches(self, path: 'str', method: 'str') -> 'tuple[Match, dict[str, Any]]'`
- `Mount(path: 'str', routes: 'list[Route]' = <factory>) -> None` class constructor
- `Router(routes: 'list[Route | Mount] | None' = None) -> 'None'` class constructor
  - `Router.match(self, path: 'str', method: 'str' = 'GET') -> 'tuple[Route | None, dict[str, Any]]'`
  - `Router.url_path_for(self, route_name: 'str', **path_params: 'Any') -> 'str'`
- `Match(*values)` class constructor
  - `Match.NONE` attribute must exist on instances

## Required Behavior

- compile_path builds a matching regex and parameter convertors, and Route distinguishes full, partial, and non-matches for the request path.
- compile_path resolves registered convertors for typed path parameters and rejects unknown convertor names.
- `Mount` matches child routes under a path prefix.
- When url_path_for is called on Route, Mount, or Router, it substitutes required parameters and raises for missing names or parameters. An unnamed Mount still reverse-resolves named child routes and prefixes the Mount path.
- The package exposes the required task API paths `featurelifted.compile_path`, `featurelifted.Route`, `featurelifted.Route.matches`, `featurelifted.Mount`, `featurelifted.Router`, `featurelifted.Router.match`, `featurelifted.Router.url_path_for`, `featurelifted.Match`, `featurelifted.Match.NONE` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `starlette`.
- Forbidden path access: `repo/, starlette/`.
- Do not implement network access.
- Do not implement ASGI server.
- Do not implement middleware/testclient.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — compile_path builds a matching regex and parameter convertors, and Route distinguishes full, partial, and non-matches for the request path.
- **B002** — compile_path resolves registered convertors for typed path parameters and rejects unknown convertor names.
- **B003** — `Mount` matches child routes under a path prefix.
- **B004** — When url_path_for is called on Route, Mount, or Router, it substitutes required parameters and raises for missing names or parameters. An unnamed Mount still reverse-resolves named child routes and prefixes the Mount path.
- **B005** — The package exposes the required task API paths `featurelifted.compile_path`, `featurelifted.Route`, `featurelifted.Route.matches`, `featurelifted.Mount`, `featurelifted.Router`, `featurelifted.Router.match`, `featurelifted.Router.url_path_for`, `featurelifted.Match`, `featurelifted.Match.NONE` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: starlette.
<!-- featureliftbench:behavior-clauses:end -->
