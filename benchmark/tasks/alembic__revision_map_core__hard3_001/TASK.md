# FeatureLift Task: RevisionMap graph, branch labels, and head resolution

Extract a task-scoped subset of `alembic` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CycleDetected,
    MissingRevision,
    MultipleHeads,
    Revision,
    RevisionMap,
)
```

## Required API Details

- `Revision(revision: 'str', down_revision: 'str | tuple[str, ...] | None' = None, dependencies: 'str | tuple[str, ...] | None' = None, branch_labels: 'set[str] | tuple[str, ...] | list[str] | None' = None) -> None` class constructor
- `RevisionMap(revisions: 'Iterable[Revision]') -> 'None'` class constructor
  - `RevisionMap.heads` attribute must exist on instances
  - `RevisionMap.bases` attribute must exist on instances
  - `RevisionMap.branch_labels` attribute must exist on instances
  - `RevisionMap.get_revision(self, identifier: 'str | None') -> 'Revision | None'`
  - `RevisionMap.get_revisions(self, identifiers) -> 'tuple[Revision | None, ...]'`
  - `RevisionMap.get_heads(self) -> 'list[str]'`
  - `RevisionMap.get_current_head(self, branch_label: 'str | None' = None) -> 'str'`
  - `RevisionMap.ancestors(self, revision_id: 'str', include_dependencies: 'bool' = True) -> 'set[str]'`
  - `RevisionMap.iterate_revisions(self, upper: 'str', lower: 'str | None' = None) -> 'list[Revision]'`
- `CycleDetected` must be importable and raisable
- `MissingRevision` must be importable and raisable
- `MultipleHeads` must be importable and raisable

## Required Behavior

- When Revision objects are created, scalar and iterable down revisions, branch labels, and dependencies are normalized without losing their distinct graph roles.
- When RevisionMap is built from explicit revisions, it links versioned parents, dependency edges, and branch labels into a queryable graph.
- For linear, branched, and merged revision graphs, RevisionMap reports the versioned bases and heads that have no versioned parent or child.
- When a branch label is assigned, branch-label lookup resolves that revision and propagates the label to eligible descendants.
- When ancestors are requested, dependency revisions are included only when dependency-aware traversal is enabled.
- When symbolic identifiers such as head or base are requested, RevisionMap resolves them and rejects ambiguous heads.
- Missing revisions, multiple-head requests, and revision cycles raise the declared explicit graph errors.
- The package exposes the required task API paths `featurelifted.Revision`, `featurelifted.RevisionMap`, `featurelifted.RevisionMap.heads`, `featurelifted.RevisionMap.bases`, `featurelifted.RevisionMap.branch_labels`, `featurelifted.RevisionMap.get_revision`, `featurelifted.RevisionMap.get_revisions`, `featurelifted.RevisionMap.get_heads`, `featurelifted.RevisionMap.get_current_head`, `featurelifted.RevisionMap.ancestors`, `featurelifted.RevisionMap.iterate_revisions`, `featurelifted.CycleDetected`, and 2 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `alembic, sqlalchemy`.
- Forbidden path access: `repo/, alembic/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement SQLAlchemy engine integration.
- Do not implement migration environment loading.
- Do not implement filesystem script directory scanning.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When Revision objects are created, scalar and iterable down revisions, branch labels, and dependencies are normalized without losing their distinct graph roles.
- **B002** — When RevisionMap is built from explicit revisions, it links versioned parents, dependency edges, and branch labels into a queryable graph.
- **B003** — For linear, branched, and merged revision graphs, RevisionMap reports the versioned bases and heads that have no versioned parent or child.
- **B004** — When a branch label is assigned, branch-label lookup resolves that revision and propagates the label to eligible descendants.
- **B005** — When ancestors are requested, dependency revisions are included only when dependency-aware traversal is enabled.
- **B006** — When symbolic identifiers such as head or base are requested, RevisionMap resolves them and rejects ambiguous heads.
- **B007** — Missing revisions, multiple-head requests, and revision cycles raise the declared explicit graph errors.
- **B008** — The package exposes the required task API paths `featurelifted.Revision`, `featurelifted.RevisionMap`, `featurelifted.RevisionMap.heads`, `featurelifted.RevisionMap.bases`, `featurelifted.RevisionMap.branch_labels`, `featurelifted.RevisionMap.get_revision`, `featurelifted.RevisionMap.get_revisions`, `featurelifted.RevisionMap.get_heads`, `featurelifted.RevisionMap.get_current_head`, `featurelifted.RevisionMap.ancestors`, `featurelifted.RevisionMap.iterate_revisions`, `featurelifted.CycleDetected`, and 2 listed members with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: alembic, sqlalchemy.
<!-- featureliftbench:behavior-clauses:end -->
