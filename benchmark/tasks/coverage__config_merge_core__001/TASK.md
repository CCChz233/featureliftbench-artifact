# FeatureLift Task: Run-section config merge

Extract a task-scoped subset of `coverage` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CoverageConfig,
    read_run_config,
)
```

## Required API Details

- `CoverageConfig() -> 'None'` class constructor
- `read_run_config(config_file: bool | str = True, warn=None, **kwargs)`

## Required Behavior

- The extracted feature must support this observable behavior: read .coveragerc and prefixed sections from setup.cfg or tox.ini. Required observable cases include read run config from coveragerc; read run config from setup cfg; read run config relative files section.
- The extracted feature must support this observable behavior: parse run include, omit, source, branch, and related list options. Required observable cases include read run config multiline lists; read run config relative files section.
- The extracted feature must support this observable behavior: merge constructor kwargs and COVERAGE_* environment overrides. Required observable cases include read run config kwargs override; read run config env data file.
- The extracted feature must support this observable behavior: apply post-processing such as user path expansion. Required observable cases include read run config relative files section.
- The package exposes the required task API paths `featurelifted.CoverageConfig`, `featurelifted.read_run_config` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `coverage`.
- Do not implement glob matching and file selection.
- Do not implement path alias remapping.
- Do not implement coverage collection, data storage, and reporting.
- Do not implement plugin loading and HTML/XML report sections beyond parsing.
- Do not implement original project tests and CLI.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: read .coveragerc and prefixed sections from setup.cfg or tox.ini. Required observable cases include read run config from coveragerc; read run config from setup cfg; read run config relative files section.
- **B002** — The extracted feature must support this observable behavior: parse run include, omit, source, branch, and related list options. Required observable cases include read run config multiline lists; read run config relative files section.
- **B003** — The extracted feature must support this observable behavior: merge constructor kwargs and COVERAGE_* environment overrides. Required observable cases include read run config kwargs override; read run config env data file.
- **B004** — The extracted feature must support this observable behavior: apply post-processing such as user path expansion. Required observable cases include read run config relative files section.
- **B005** — The package exposes the required task API paths `featurelifted.CoverageConfig`, `featurelifted.read_run_config` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: coverage.
<!-- featureliftbench:behavior-clauses:end -->
