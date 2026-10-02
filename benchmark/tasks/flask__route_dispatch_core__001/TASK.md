# FeatureLift Task: Application route registration and dispatch

Extract a task-scoped subset of `flask` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    App,
    Response,
)
```

## Required API Details

- `App(name)` class constructor
  - `App.dispatch(self, path, method='GET')`
  - `App.errorhandler(self, code)`
  - `App.route(self, rule, methods=None)`
- `Response(body: object, status_code: int = 200, headers: dict = <factory>) -> None` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: route decorator registration for static, string, and int path segments. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- The extracted feature must support this observable behavior: method-aware dispatch with GET default. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- The extracted feature must support this observable behavior: Response normalization for strings, tuples, and Response values. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- The extracted feature must support this observable behavior: 404 and 405 error-handler dispatch. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- The package exposes the required task API paths `featurelifted.App`, `featurelifted.App.dispatch`, `featurelifted.App.errorhandler`, `featurelifted.App.route`, `featurelifted.Response` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `flask`.
- Forbidden path access: `repo/, flask/`.
- Do not implement WSGI server.
- Do not implement request globals.
- Do not implement templates.
- Do not implement sessions.
- Do not implement blueprints.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: route decorator registration for static, string, and int path segments. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- **B002** — The extracted feature must support this observable behavior: method-aware dispatch with GET default. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- **B003** — The extracted feature must support this observable behavior: Response normalization for strings, tuples, and Response values. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- **B004** — The extracted feature must support this observable behavior: 404 and 405 error-handler dispatch. Required observable cases include static and typed routes; method dispatch; string converter and response passthrough; error handlers.
- **B005** — The package exposes the required task API paths `featurelifted.App`, `featurelifted.App.dispatch`, `featurelifted.App.errorhandler`, `featurelifted.App.route`, `featurelifted.Response` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: flask.
<!-- featureliftbench:behavior-clauses:end -->
