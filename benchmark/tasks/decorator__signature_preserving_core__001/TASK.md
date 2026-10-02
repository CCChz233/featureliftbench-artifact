# FeatureLift Task: Signature-preserving function decorator

Extract a task-scoped subset of `decorator` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    decorate,
    decorator,
)
```

## Required API Details

- `decorate(func, caller)`
- `decorator(caller, func=None)`

## Required Behavior

- The extracted feature must support this observable behavior: caller receives the original function before bound arguments. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- The extracted feature must support this observable behavior: decorated call enforces the original function signature. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- The extracted feature must support this observable behavior: name, docstring, module, annotations, wrapped, and inspect.signature are preserved. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- The extracted feature must support this observable behavior: async callers and coroutine functions remain awaitable. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- The package exposes the required task API paths `featurelifted.decorate`, `featurelifted.decorator` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `decorator`.
- Forbidden path access: `repo/, decorator/`.
- Do not implement contextmanager helpers.
- Do not implement FunctionMaker source generation.
- Do not implement class decoration.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: caller receives the original function before bound arguments. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- **B002** — The extracted feature must support this observable behavior: decorated call enforces the original function signature. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- **B003** — The extracted feature must support this observable behavior: name, docstring, module, annotations, wrapped, and inspect.signature are preserved. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- **B004** — The extracted feature must support this observable behavior: async callers and coroutine functions remain awaitable. Required observable cases include metadata signature and call order; invalid calls follow original signature; async caller and wrapped.
- **B005** — The package exposes the required task API paths `featurelifted.decorate`, `featurelifted.decorator` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: decorator.
<!-- featureliftbench:behavior-clauses:end -->
