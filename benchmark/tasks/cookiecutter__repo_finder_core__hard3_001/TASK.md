# FeatureLift Task: RepoFinder

Extract a task-scoped subset of `cookiecutter` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    expand_abbreviation,
    RepoFinder,
    safe_join,
    UnsafePathError,
)
```

## Required API Details

- `RepoFinder(*, abbreviations: 'dict[str, str] | None' = None, template_root: 'str' = '/templates', replay_dir: 'str' = '/replay') -> 'None'` class constructor
  - `RepoFinder.find_template(self, repo_spec: 'str', replay: 'dict[str, str] | None' = None) -> 'dict[str, str | bool]'`
- `expand_abbreviation(repo: 'str', abbreviations: 'dict[str, str]') -> 'str'`
- `safe_join(base: 'str', *parts: 'str') -> 'str'`
- `UnsafePathError` must be importable and raisable

## Required Behavior

- When a repository abbreviation is supplied, expand_abbreviation and RepoFinder expand it using configured abbreviations before resolving the template path.
- Abbreviations expand short repo prefixes; replay overrides take precedence.
- `safe_join` rejects path traversal and absolute segments.
- The package exposes the required task API paths `featurelifted.RepoFinder`, `featurelifted.RepoFinder.find_template`, `featurelifted.expand_abbreviation`, `featurelifted.safe_join`, `featurelifted.UnsafePathError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `cookiecutter`.
- Forbidden path access: `repo/, cookiecutter/`.
- Do not implement network access.
- Do not implement git download.
- Do not implement template rendering.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — When a repository abbreviation is supplied, expand_abbreviation and RepoFinder expand it using configured abbreviations before resolving the template path.
- **B002** — Abbreviations expand short repo prefixes; replay overrides take precedence.
- **B003** — `safe_join` rejects path traversal and absolute segments.
- **B004** — The package exposes the required task API paths `featurelifted.RepoFinder`, `featurelifted.RepoFinder.find_template`, `featurelifted.expand_abbreviation`, `featurelifted.safe_join`, `featurelifted.UnsafePathError` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: cookiecutter.
<!-- featureliftbench:behavior-clauses:end -->
