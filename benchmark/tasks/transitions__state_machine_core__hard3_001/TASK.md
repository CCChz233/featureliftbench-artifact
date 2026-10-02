# FeatureLift Task: Hierarchical state machine transition core

Extract a task-scoped subset of `transitions` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Machine,
    MachineError,
)
```

## Required API Details

- `MachineError` must be importable and raisable
- `Machine(model: 'Any', states: 'list[str] | None' = None, initial: 'str' = 'initial', transitions: 'list[dict] | None' = None, before_state_change: 'list[str] | None' = None, after_state_change: 'list[str] | None' = None, ignore_invalid_triggers: 'bool' = False, send_event: 'bool' = False, auto_transitions: 'bool' = False) -> 'None'` class constructor
  - `Machine.__init__(self, model: 'Any', states: 'list[str] | None' = None, initial: 'str' = 'initial', transitions: 'list[dict] | None' = None, before_state_change: 'list[str] | None' = None, after_state_change: 'list[str] | None' = None, ignore_invalid_triggers: 'bool' = False, send_event: 'bool' = False, auto_transitions: 'bool' = False) -> 'None'`

## Required Behavior

- When a registered trigger method is invoked on a model, the machine executes the matching transition and updates model.state.
- When a transition declares conditions, the transition is skipped unless every condition callable returns a truthy value.
- When transition before/after callbacks are configured, they run around the state change in upstream order.
- When a machine is created with a dotted nested state name such as parent.child, the model exposes the nested hierarchy such that model.parent.state == "child".
- The package exposes the required task API paths `featurelifted.MachineError`, `featurelifted.Machine`, `featurelifted.Machine.__init__` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `transitions`.
- Forbidden path access: `repo/, transitions/`.
- Do not implement network access.
- Do not implement async transitions.
- Do not implement graphviz extensions.
- Do not implement diagram rendering.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When a registered trigger method is invoked on a model, the machine executes the matching transition and updates model.state.
- **B002** — When a transition declares conditions, the transition is skipped unless every condition callable returns a truthy value.
- **B003** — When transition before/after callbacks are configured, they run around the state change in upstream order.
- **B004** — When a machine is created with a dotted nested state name such as parent.child, the model exposes the nested hierarchy such that model.parent.state == "child".
- **B005** — The package exposes the required task API paths `featurelifted.MachineError`, `featurelifted.Machine`, `featurelifted.Machine.__init__` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: transitions.
<!-- featureliftbench:behavior-clauses:end -->
