# FeatureLift Task: Cobertura XML report writer

Extract a task-scoped subset of `coverage` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Analysis,
    CoverageConfig,
    rate,
    serialize_xml,
    XmlReporter,
)
```

## Required API Details

- `Analysis(precision: 'int', filename: 'str', has_arcs: 'bool', statements: 'set[TLineNo]', excluded: 'set[TLineNo]', executed: 'set[TLineNo]', arc_possibilities_set: 'set[TArc]', arcs_executed_set: 'set[TArc]', exit_counts: 'dict[TLineNo, int]', no_branch: 'set[TLineNo]') -> None` class constructor
- `CoverageConfig() -> 'None'` class constructor
  - `CoverageConfig.skip_empty` attribute must exist on instances
  - `CoverageConfig.xml_package_depth` attribute must exist on instances
- `XmlReporter(coverage: 'Coverage') -> 'None'` class constructor
  - `XmlReporter.report` attribute must exist on instances
  - `XmlReporter.packages` attribute must exist on instances
  - `XmlReporter.xml_file(self, fr: 'FileReporter', analysis: 'Analysis', has_arcs: 'bool') -> 'None'`
  - `XmlReporter.xml_out` attribute must exist on instances
- `rate(hit: 'int', num: 'int') -> 'str'`
- `serialize_xml(dom: 'xml.dom.minidom.Document') -> 'str'`

## Required Behavior

- The extracted feature must support this observable behavior: emit Cobertura-compatible XML with coverage, packages, and classes. Required observable cases include xml file emits line elements; serialize xml produces coverage root.
- The extracted feature must support this observable behavior: serialize line and branch hit information from Analysis objects. Required observable cases include xml file emits line elements; xml package depth truncates package name.
- The extracted feature must support this observable behavior: honor xml_package_depth and skip_empty config options. Required observable cases include xml package depth truncates package name; skip empty omits zero statement files.
- The extracted feature must support this observable behavior: compute line-rate and branch-rate attributes. Required observable cases include rate handles zero and fraction; xml package depth truncates package name.
- The package exposes the required task API paths `featurelifted.Analysis`, `featurelifted.CoverageConfig`, `featurelifted.CoverageConfig.skip_empty`, `featurelifted.CoverageConfig.xml_package_depth`, `featurelifted.XmlReporter`, `featurelifted.XmlReporter.report`, `featurelifted.XmlReporter.packages`, `featurelifted.XmlReporter.xml_file`, `featurelifted.XmlReporter.xml_out`, `featurelifted.rate`, `featurelifted.serialize_xml` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `coverage`.
- Do not implement coverage data collection and measurement.
- Do not implement HTML/JSON/LCOV report writers.
- Do not implement configuration file discovery beyond CoverageConfig fields.
- Do not implement plugin loading and CLI entrypoints.
- Do not implement original project tests and docs.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: emit Cobertura-compatible XML with coverage, packages, and classes. Required observable cases include xml file emits line elements; serialize xml produces coverage root.
- **B002** — The extracted feature must support this observable behavior: serialize line and branch hit information from Analysis objects. Required observable cases include xml file emits line elements; xml package depth truncates package name.
- **B003** — The extracted feature must support this observable behavior: honor xml_package_depth and skip_empty config options. Required observable cases include xml package depth truncates package name; skip empty omits zero statement files.
- **B004** — The extracted feature must support this observable behavior: compute line-rate and branch-rate attributes. Required observable cases include rate handles zero and fraction; xml package depth truncates package name.
- **B005** — The package exposes the required task API paths `featurelifted.Analysis`, `featurelifted.CoverageConfig`, `featurelifted.CoverageConfig.skip_empty`, `featurelifted.CoverageConfig.xml_package_depth`, `featurelifted.XmlReporter`, `featurelifted.XmlReporter.report`, `featurelifted.XmlReporter.packages`, `featurelifted.XmlReporter.xml_file`, `featurelifted.XmlReporter.xml_out`, `featurelifted.rate`, `featurelifted.serialize_xml` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: coverage.
<!-- featureliftbench:behavior-clauses:end -->
