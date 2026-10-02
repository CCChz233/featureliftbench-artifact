# FeatureLift Task: Signal receiver registry

Extract a task-scoped subset of `blinker` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ANY,
    Namespace,
    Signal,
)
```

## Required API Details

- `ANY` constant must exist
- `Namespace(*args, **kwargs)` class constructor
- `Signal(doc=None)` class constructor
  - `Signal.connect(self, receiver, sender=<object object>, weak=True)`
  - `Signal.send(self, sender=None, **kwargs)`

## Required Behavior

- The extracted feature must support this observable behavior: connect, disconnect, connected_to, and receiver iteration. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- The extracted feature must support this observable behavior: ANY and sender-specific dispatch. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- The extracted feature must support this observable behavior: weak receiver cleanup after garbage collection. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- The extracted feature must support this observable behavior: Namespace returns one stable Signal per name. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- The package exposes the required task API paths `featurelifted.ANY`, `featurelifted.Namespace`, `featurelifted.Signal`, `featurelifted.Signal.connect`, `featurelifted.Signal.send` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `blinker`.
- Forbidden path access: `repo/, blinker/`.
- Do not implement async receivers.
- Do not implement global named signal singleton.
- Do not implement documentation helpers.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: connect, disconnect, connected_to, and receiver iteration. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- **B002** — The extracted feature must support this observable behavior: ANY and sender-specific dispatch. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- **B003** — The extracted feature must support this observable behavior: weak receiver cleanup after garbage collection. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- **B004** — The extracted feature must support this observable behavior: Namespace returns one stable Signal per name. Required observable cases include sender filtering and responses; namespace identity; weak receiver cleanup; connected to scope and disconnect.
- **B005** — The package exposes the required task API paths `featurelifted.ANY`, `featurelifted.Namespace`, `featurelifted.Signal`, `featurelifted.Signal.connect`, `featurelifted.Signal.send` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: blinker.
<!-- featureliftbench:behavior-clauses:end -->
