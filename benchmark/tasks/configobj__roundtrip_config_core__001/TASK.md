# FeatureLift Task: INI-like config round-trip and configspec validation

Extract a task-scoped subset of `configobj` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ConfigObj,
    DuplicateError,
    flatten_errors,
    get_extra_values,
    validate,
)
```

## Required API Details

- `ConfigObj(infile=None, options=None, configspec=None, encoding=None, interpolation=True, raise_errors=False, list_values=True, create_empty=False, file_error=False, stringify=True, indent_type=None, default_encoding=None, unrepr=False, write_empty_values=False, _inspec=False)` class constructor
  - `ConfigObj.validate(self, validator, preserve_errors=False, copy=False, section=None)`
  - `ConfigObj.write(self, outfile=None, section=None)`
  - `ConfigObj.__getitem__(self, key)`
- `DuplicateError` must be importable and raisable
- `flatten_errors(cfg, res, levels=None, results=None)`
- `get_extra_values(conf, _prepend=())`
- `validate` module must be importable
  - `validate.Validator(functions=None)` class constructor
  - `validate.VdtValueTooSmallError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse INI-like config from strings with nested sections. Required observable cases include parse sections and values; no configobj import surface.
- The extracted feature must support this observable behavior: write configs preserving comments and key order metadata. Required observable cases include write roundtrip keys; scalar order metadata; comment preserved on write.
- The extracted feature must support this observable behavior: validate values against configspec via Validator. Required observable cases include configspec validation failure flattened; get extra values from configspec.
- The extracted feature must support this observable behavior: report validation failures with flatten_errors. Required observable cases include configspec validation failure flattened.
- The extracted feature must support this observable behavior: detect duplicate sections and parse errors. Required observable cases include parse sections and values; duplicate section raises.
- The package exposes the required task API paths `featurelifted.ConfigObj`, `featurelifted.ConfigObj.validate`, `featurelifted.ConfigObj.write`, `featurelifted.ConfigObj.__getitem__`, `featurelifted.DuplicateError`, `featurelifted.flatten_errors`, `featurelifted.get_extra_values`, `featurelifted.validate`, `featurelifted.validate.Validator`, `featurelifted.validate.VdtValueTooSmallError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `configobj`.
- Do not implement original configobj import at runtime.
- Do not implement project tests and packaging.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse INI-like config from strings with nested sections. Required observable cases include parse sections and values; no configobj import surface.
- **B002** — The extracted feature must support this observable behavior: write configs preserving comments and key order metadata. Required observable cases include write roundtrip keys; scalar order metadata; comment preserved on write.
- **B003** — The extracted feature must support this observable behavior: validate values against configspec via Validator. Required observable cases include configspec validation failure flattened; get extra values from configspec.
- **B004** — The extracted feature must support this observable behavior: report validation failures with flatten_errors. Required observable cases include configspec validation failure flattened.
- **B005** — The extracted feature must support this observable behavior: detect duplicate sections and parse errors. Required observable cases include parse sections and values; duplicate section raises.
- **B006** — The package exposes the required task API paths `featurelifted.ConfigObj`, `featurelifted.ConfigObj.validate`, `featurelifted.ConfigObj.write`, `featurelifted.ConfigObj.__getitem__`, `featurelifted.DuplicateError`, `featurelifted.flatten_errors`, `featurelifted.get_extra_values`, `featurelifted.validate`, `featurelifted.validate.Validator`, `featurelifted.validate.VdtValueTooSmallError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: configobj.
<!-- featureliftbench:behavior-clauses:end -->
