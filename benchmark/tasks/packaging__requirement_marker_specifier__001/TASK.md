# FeatureLift Task: Python package requirement, marker, specifier, and version semantics

Extract a task-scoped subset of `packaging` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    default_environment,
    InvalidMarker,
    InvalidRequirement,
    InvalidSpecifier,
    InvalidVersion,
    Marker,
    Requirement,
    Specifier,
    SpecifierSet,
    Version,
)
```

## Required API Details

- `Version(version: 'str') -> 'None'` class constructor
- `Specifier(spec: 'str' = '', prereleases: 'bool | None' = None) -> 'None'` class constructor
- `SpecifierSet(specifiers: 'str' = '', prereleases: 'bool | None' = None) -> 'None'` class constructor
  - `SpecifierSet.filter(self, iterable: 'Iterable[UnparsedVersionVar]', prereleases: 'bool | None' = None) -> 'Iterator[UnparsedVersionVar]'`
  - `SpecifierSet.__contains__(self, item: 'UnparsedVersion') -> 'bool'`
- `Requirement(requirement_string: 'str') -> 'None'` class constructor
  - `Requirement.extras` attribute must exist on instances
  - `Requirement.marker` attribute must exist on instances
  - `Requirement.name` attribute must exist on instances
  - `Requirement.specifier` attribute must exist on instances
  - `Requirement.url` attribute must exist on instances
- `Marker(marker: 'str') -> 'None'` class constructor
  - `Marker.evaluate(self, environment: 'dict[str, str] | None' = None) -> 'bool'`
- `default_environment() -> 'Environment'`
- `InvalidVersion` must be importable and raisable
- `InvalidSpecifier` must be importable and raisable
- `InvalidRequirement` must be importable and raisable
- `InvalidMarker` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse, normalize, compare, hash, and stringify PEP 440 versions including epochs, post releases, pre releases, dev releases, and local versions. Required observable cases include versions and specifiers basic semantics; version normalization ordering and invalid inputs.
- The extracted feature must support this observable behavior: parse and evaluate specifier sets including compatible release, equality wildcard, exclusion, prerelease handling, filtering, and containment. Required observable cases include versions and specifiers basic semantics; specifier prerelease wildcard compatible and filtering.
- The extracted feature must support this observable behavior: parse PEP 508 requirements with extras, URL requirements, specifiers, and environment markers. Required observable cases include requirements and markers api; invalid requirement is rejected; requirement urls extras and marker evaluation.
- The extracted feature must support this observable behavior: parse and evaluate environment markers with and/or grouping, in/not in operators, extra handling, and default environment values. Required observable cases include requirements and markers api; marker boolean logic default environment and errors.
- The extracted feature must support this observable behavior: raise stable InvalidVersion, InvalidSpecifier, InvalidRequirement, and InvalidMarker errors for malformed input. Required observable cases include version normalization ordering and invalid inputs.
- The package exposes the required task API paths `featurelifted.Version`, `featurelifted.Specifier`, `featurelifted.SpecifierSet`, `featurelifted.SpecifierSet.filter`, `featurelifted.SpecifierSet.__contains__`, `featurelifted.Requirement`, `featurelifted.Requirement.extras`, `featurelifted.Requirement.marker`, `featurelifted.Requirement.name`, `featurelifted.Requirement.specifier`, `featurelifted.Requirement.url`, `featurelifted.Marker`, and 6 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `packaging`.
- Do not implement wheel tag generation and compatibility tags.
- Do not implement manylinux and musllinux platform probing.
- Do not implement package metadata validation.
- Do not implement filename and sdist/wheel utility helpers outside the required entrypoints.
- Do not implement original project tests, documentation, and release tooling.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse, normalize, compare, hash, and stringify PEP 440 versions including epochs, post releases, pre releases, dev releases, and local versions. Required observable cases include versions and specifiers basic semantics; version normalization ordering and invalid inputs.
- **B002** — The extracted feature must support this observable behavior: parse and evaluate specifier sets including compatible release, equality wildcard, exclusion, prerelease handling, filtering, and containment. Required observable cases include versions and specifiers basic semantics; specifier prerelease wildcard compatible and filtering.
- **B003** — The extracted feature must support this observable behavior: parse PEP 508 requirements with extras, URL requirements, specifiers, and environment markers. Required observable cases include requirements and markers api; invalid requirement is rejected; requirement urls extras and marker evaluation.
- **B004** — The extracted feature must support this observable behavior: parse and evaluate environment markers with and/or grouping, in/not in operators, extra handling, and default environment values. Required observable cases include requirements and markers api; marker boolean logic default environment and errors.
- **B005** — The extracted feature must support this observable behavior: raise stable InvalidVersion, InvalidSpecifier, InvalidRequirement, and InvalidMarker errors for malformed input. Required observable cases include version normalization ordering and invalid inputs.
- **B006** — The package exposes the required task API paths `featurelifted.Version`, `featurelifted.Specifier`, `featurelifted.SpecifierSet`, `featurelifted.SpecifierSet.filter`, `featurelifted.SpecifierSet.__contains__`, `featurelifted.Requirement`, `featurelifted.Requirement.extras`, `featurelifted.Requirement.marker`, `featurelifted.Requirement.name`, `featurelifted.Requirement.specifier`, `featurelifted.Requirement.url`, `featurelifted.Marker`, and 6 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: packaging.
<!-- featureliftbench:behavior-clauses:end -->
