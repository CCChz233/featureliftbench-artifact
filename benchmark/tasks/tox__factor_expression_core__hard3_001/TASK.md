# FeatureLift Task: Environment factor expression and ini filtering

Extract a task-scoped subset of `tox` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    expand_factors,
    filter_for_env,
    find_envs,
)
```

## Required API Details

- `expand_factors(value: 'str') -> 'Iterator[tuple[list[list[tuple[str, bool]]] | None, str]]'`
- `find_envs(value: 'str') -> 'list[str]'`
- `filter_for_env(value: 'str', env_name: 'str | None', env_factors: 'set[str] | None' = None) -> 'str'`

## Required Behavior

- `find_envs` discovers environment names from brace factor expressions.
- When factor expressions contain negation, filter_for_env accepts an environment only when positive factors match and negated factors do not.
- find_envs expands brace and factor expressions into the deterministic set of environment names they describe.
- `filter_for_env` keeps lines whose factor expressions match `env_name` and/or `env_factors`.
- The package exposes the required task API paths `featurelifted.expand_factors`, `featurelifted.find_envs`, `featurelifted.filter_for_env` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `tox`.
- Forbidden path access: `repo/, tox/`.
- Do not implement network access.
- Do not implement virtualenv creation.
- Do not implement subprocess execution.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `find_envs` discovers environment names from brace factor expressions.
- **B002** — When factor expressions contain negation, filter_for_env accepts an environment only when positive factors match and negated factors do not.
- **B003** — find_envs expands brace and factor expressions into the deterministic set of environment names they describe.
- **B004** — `filter_for_env` keeps lines whose factor expressions match `env_name` and/or `env_factors`.
- **B005** — The package exposes the required task API paths `featurelifted.expand_factors`, `featurelifted.find_envs`, `featurelifted.filter_for_env` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: tox.
<!-- featureliftbench:behavior-clauses:end -->
