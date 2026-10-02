# FeatureLift Task: Source/include/omit selection

Extract a task-scoped subset of `coverage` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    SourceSelector,
)
```

## Required API Details

- `SourceSelector(*, source: 'list[str] | None' = None, source_pkgs: 'list[str] | None' = None, run_include: 'list[str] | None' = None, run_omit: 'list[str] | None' = None, cover_pylib: 'bool' = False) -> 'None'` class constructor
  - `SourceSelector.skip_reason(self, filename: 'str', modulename: 'str | None' = None) -> 'str | None'`

## Required Behavior

- The extracted feature must support this observable behavior: honor --source directory and package specifications. Required observable cases include source selector honors source tree; source selector honors omit; source selector rejects non utf8 filename.
- The extracted feature must support this observable behavior: apply run include and omit glob patterns after source scoping. Required observable cases include source selector honors omit; source selector package name; source selector include without source; source selector omit wins over include.
- The extracted feature must support this observable behavior: exclude stdlib, third-party, and coverage.py paths when no source is set. Required observable cases include source selector package name; source selector rejects non utf8 filename.
- The extracted feature must support this observable behavior: return human-readable skip reasons for rejected files. Required observable cases include source selector rejects non utf8 filename.
- The package exposes the required task API paths `featurelifted.SourceSelector`, `featurelifted.SourceSelector.skip_reason` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `coverage`.
- Do not implement plugin file tracers and dynamic source filenames.
- Do not implement coverage data collection and reporting.
- Do not implement path alias remapping for combine.
- Do not implement configuration file discovery beyond constructing a config object.
- Do not implement original project tests and CLI.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: honor --source directory and package specifications. Required observable cases include source selector honors source tree; source selector honors omit; source selector rejects non utf8 filename.
- **B002** — The extracted feature must support this observable behavior: apply run include and omit glob patterns after source scoping. Required observable cases include source selector honors omit; source selector package name; source selector include without source; source selector omit wins over include.
- **B003** — The extracted feature must support this observable behavior: exclude stdlib, third-party, and coverage.py paths when no source is set. Required observable cases include source selector package name; source selector rejects non utf8 filename.
- **B004** — The extracted feature must support this observable behavior: return human-readable skip reasons for rejected files. Required observable cases include source selector rejects non utf8 filename.
- **B005** — The package exposes the required task API paths `featurelifted.SourceSelector`, `featurelifted.SourceSelector.skip_reason` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: coverage.
<!-- featureliftbench:behavior-clauses:end -->
