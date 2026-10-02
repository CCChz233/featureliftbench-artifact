# FeatureLift Task: version_from_scm

Extract a task-scoped subset of `setuptools_scm` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    version_from_scm,
)
```

## Required API Details

- `version_from_scm(root, *, tag: 'str' = 'v1.0.0', distance: 'int' = 0, dirty: 'bool' = False, node: 'str' = 'g1234567') -> 'str'`

## Required Behavior

- version_from_scm normalizes SCM-style tags into a valid base version and incorporates distance, dirty state, and node information.
- When distance from the tag is positive, version_from_scm appends the corresponding development-distance suffix.
- When node or dirty information is present, version_from_scm appends a local version segment that includes the node hash and, when dirty=True, a dirty marker. The local segment is not required to use a g prefix or to omit .dirty.
- The package exposes the required task API paths `featurelifted.version_from_scm` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `setuptools_scm`.
- Forbidden path access: `repo/, setuptools_scm/`.
- Do not implement network access.
- Do not implement subprocess git/hg.
- Do not implement full setuptools integration.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — version_from_scm normalizes SCM-style tags into a valid base version and incorporates distance, dirty state, and node information.
- **B002** — When distance from the tag is positive, version_from_scm appends the corresponding development-distance suffix.
- **B003** — When node or dirty information is present, version_from_scm appends a local version segment that includes the node hash and, when dirty=True, a dirty marker. The local segment is not required to use a g prefix or to omit .dirty.
- **B004** — The package exposes the required task API paths `featurelifted.version_from_scm` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: setuptools_scm.
<!-- featureliftbench:behavior-clauses:end -->
