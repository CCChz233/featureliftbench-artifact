# FeatureLift Task: Entry point discovery and selection

Extract a task-scoped subset of `importlib_metadata` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    EntryPoint,
    EntryPoints,
    PathDistribution,
    Sectioned,
)
```

## Required API Details

- `EntryPoint(name: 'str', value: 'str', group: 'str') -> 'None'` class constructor
  - `EntryPoint.name` attribute must exist on instances
  - `EntryPoint.value` attribute must exist on instances
  - `EntryPoint.attr` attribute must exist on instances
  - `EntryPoint.module` attribute must exist on instances
- `EntryPoints(iterable=(), /)` class constructor
  - `EntryPoints.select(self, **params)`
  - `EntryPoints.__getitem__(self, name: 'str') -> 'EntryPoint'`
- `PathDistribution(path: 'SimplePath') -> 'None'` class constructor
  - `PathDistribution.entry_points` attribute must exist on instances
- `Sectioned()` class constructor
  - `Sectioned.section_pairs(text)`

## Required Behavior

- The extracted feature must support this observable behavior: parse entry point definitions from metadata. Required observable cases include path distribution entry points.
- The extracted feature must support this observable behavior: select entry points by group and name. Required observable cases include entry point value parsing and selection; path distribution entry points.
- The extracted feature must support this observable behavior: load entry point targets. Required observable cases include path distribution entry points.
- The extracted feature must support this observable behavior: read entry points from PathDistribution metadata directories. Required observable cases include path distribution entry points.
- The extracted feature must support this observable behavior: parse INI-style sectioned entry point config. Required observable cases include entry point value parsing and selection; sectioned entry point config; path distribution entry points.
- The package exposes the required task API paths `featurelifted.EntryPoint`, `featurelifted.EntryPoint.name`, `featurelifted.EntryPoint.value`, `featurelifted.EntryPoint.attr`, `featurelifted.EntryPoint.module`, `featurelifted.EntryPoints`, `featurelifted.EntryPoints.select`, `featurelifted.EntryPoints.__getitem__`, `featurelifted.PathDistribution`, `featurelifted.PathDistribution.entry_points`, `featurelifted.Sectioned`, `featurelifted.Sectioned.section_pairs` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `importlib_metadata`.
- Do not implement full distribution discovery across sys.path.
- Do not implement package file listing and requirements resolution.
- Do not implement original project tests and CLI.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse entry point definitions from metadata. Required observable cases include path distribution entry points.
- **B002** — The extracted feature must support this observable behavior: select entry points by group and name. Required observable cases include entry point value parsing and selection; path distribution entry points.
- **B003** — The extracted feature must support this observable behavior: load entry point targets. Required observable cases include path distribution entry points.
- **B004** — The extracted feature must support this observable behavior: read entry points from PathDistribution metadata directories. Required observable cases include path distribution entry points.
- **B005** — The extracted feature must support this observable behavior: parse INI-style sectioned entry point config. Required observable cases include entry point value parsing and selection; sectioned entry point config; path distribution entry points.
- **B006** — The package exposes the required task API paths `featurelifted.EntryPoint`, `featurelifted.EntryPoint.name`, `featurelifted.EntryPoint.value`, `featurelifted.EntryPoint.attr`, `featurelifted.EntryPoint.module`, `featurelifted.EntryPoints`, `featurelifted.EntryPoints.select`, `featurelifted.EntryPoints.__getitem__`, `featurelifted.PathDistribution`, `featurelifted.PathDistribution.entry_points`, `featurelifted.Sectioned`, `featurelifted.Sectioned.section_pairs` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: importlib_metadata.
<!-- featureliftbench:behavior-clauses:end -->
