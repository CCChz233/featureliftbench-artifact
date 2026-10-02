# FeatureLift Task: Phone number parse and format

Extract a task-scoped subset of `phonenumbers` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    format_number,
    is_valid_number,
    NumberParseException,
    parse,
    PhoneNumberFormat,
    phonenumberutil,
)
```

## Required API Details

- `PhoneNumberFormat()` class constructor
  - `PhoneNumberFormat.E164` attribute must exist on instances
  - `PhoneNumberFormat.INTERNATIONAL` attribute must exist on instances
  - `PhoneNumberFormat.NATIONAL` attribute must exist on instances
- `NumberParseException` must be importable and raisable
- `format_number(numobj, num_format)`
- `is_valid_number(numobj)`
- `parse(number, region=None, keep_raw_input=False, numobj=None, _check_region=True)`
- `phonenumberutil` module must be importable
  - `phonenumberutil.NumberParseException` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse E.164 and national numbers for US and GB. Required observable cases include parse e164 and format; parse national us; gb national equals e164 parse; is valid and e164 us.
- The extracted feature must support this observable behavior: format NATIONAL, INTERNATIONAL, and E164. Required observable cases include parse e164 and format; is valid and e164 us.
- The extracted feature must support this observable behavior: validate numbers against region metadata. Required observable cases include invalid region raises.
- The package exposes the required task API paths `featurelifted.PhoneNumberFormat`, `featurelifted.PhoneNumberFormat.E164`, `featurelifted.PhoneNumberFormat.INTERNATIONAL`, `featurelifted.PhoneNumberFormat.NATIONAL`, `featurelifted.NumberParseException`, `featurelifted.format_number`, `featurelifted.is_valid_number`, `featurelifted.parse`, `featurelifted.phonenumberutil`, `featurelifted.phonenumberutil.NumberParseException` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `phonenumbers`.
- Do not implement full global geodata/carrier/timezone datasets.
- Do not implement PhoneNumberMatcher and short-number data.
- Do not implement original phonenumbers import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse E.164 and national numbers for US and GB. Required observable cases include parse e164 and format; parse national us; gb national equals e164 parse; is valid and e164 us.
- **B002** — The extracted feature must support this observable behavior: format NATIONAL, INTERNATIONAL, and E164. Required observable cases include parse e164 and format; is valid and e164 us.
- **B003** — The extracted feature must support this observable behavior: validate numbers against region metadata. Required observable cases include invalid region raises.
- **B004** — The package exposes the required task API paths `featurelifted.PhoneNumberFormat`, `featurelifted.PhoneNumberFormat.E164`, `featurelifted.PhoneNumberFormat.INTERNATIONAL`, `featurelifted.PhoneNumberFormat.NATIONAL`, `featurelifted.NumberParseException`, `featurelifted.format_number`, `featurelifted.is_valid_number`, `featurelifted.parse`, `featurelifted.phonenumberutil`, `featurelifted.phonenumberutil.NumberParseException` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: phonenumbers.
<!-- featureliftbench:behavior-clauses:end -->
