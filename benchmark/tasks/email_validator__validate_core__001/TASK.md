# FeatureLift Task: Email syntax validation core

Extract a task-scoped subset of `email_validator` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    EmailNotValidError,
    EmailSyntaxError,
    EmailUndeliverableError,
    validate_email,
    ValidatedEmail,
)
```

## Required API Details

- `validate_email` module must be importable
- `ValidatedEmail()` class constructor
- `EmailNotValidError` must be importable and raisable
- `EmailSyntaxError` must be importable and raisable
- `EmailUndeliverableError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: validate_email returns ValidatedEmail with normalized/local_part/domain fields. Required observable cases include validate basic ascii email; validate plus addressing; invalid empty local part; quoted local part dequoted; smtputf8 local part; domain literal ipv4.
- The extracted feature must support this observable behavior: EmailSyntaxError and EmailNotValidError for invalid addresses. Required observable cases include invalid missing at sign; unicode nfc local part.
- The extracted feature must support this observable behavior: IDNA domain encoding and internationalized local parts (SMTPUTF8). Required observable cases include idna domain normalization; smtputf8 local part.
- The extracted feature must support this observable behavior: quoted local part parsing and de-quoting when allowed. Required observable cases include quoted local part dequoted.
- The extracted feature must support this observable behavior: display name angle-bracket parsing when allowed. Required observable cases include display name parsing; test environment allows dot test.
- The extracted feature must support this observable behavior: reserved/special-use domain rejection and test_environment bypass. Required observable cases include reserved domain rejected; test environment allows dot test; domain literal ipv4.
- The extracted feature must support this observable behavior: case-insensitive mailbox names (e.g. POSTMASTER). Required observable cases include postmaster case insensitive.
- The extracted feature must support this observable behavior: Unicode NFC normalization of local parts. Required observable cases include invalid empty local part; unicode nfc local part.
- The package exposes the required task API paths `featurelifted.validate_email`, `featurelifted.ValidatedEmail`, `featurelifted.EmailNotValidError`, `featurelifted.EmailSyntaxError`, `featurelifted.EmailUndeliverableError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `email_validator, emailvalidator, dns`.
- Do not implement DNS deliverability checks and caching_resolver.
- Do not implement CLI entry point (__main__).
- Do not implement original email_validator import at runtime.
- Do not implement network access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: validate_email returns ValidatedEmail with normalized/local_part/domain fields. Required observable cases include validate basic ascii email; validate plus addressing; invalid empty local part; quoted local part dequoted; smtputf8 local part; domain literal ipv4.
- **B002** — The extracted feature must support this observable behavior: EmailSyntaxError and EmailNotValidError for invalid addresses. Required observable cases include invalid missing at sign; unicode nfc local part.
- **B003** — The extracted feature must support this observable behavior: IDNA domain encoding and internationalized local parts (SMTPUTF8). Required observable cases include idna domain normalization; smtputf8 local part.
- **B004** — The extracted feature must support this observable behavior: quoted local part parsing and de-quoting when allowed. Required observable cases include quoted local part dequoted.
- **B005** — The extracted feature must support this observable behavior: display name angle-bracket parsing when allowed. Required observable cases include display name parsing; test environment allows dot test.
- **B006** — The extracted feature must support this observable behavior: reserved/special-use domain rejection and test_environment bypass. Required observable cases include reserved domain rejected; test environment allows dot test; domain literal ipv4.
- **B007** — The extracted feature must support this observable behavior: case-insensitive mailbox names (e.g. POSTMASTER). Required observable cases include postmaster case insensitive.
- **B008** — The extracted feature must support this observable behavior: Unicode NFC normalization of local parts. Required observable cases include invalid empty local part; unicode nfc local part.
- **B009** — The package exposes the required task API paths `featurelifted.validate_email`, `featurelifted.ValidatedEmail`, `featurelifted.EmailNotValidError`, `featurelifted.EmailSyntaxError`, `featurelifted.EmailUndeliverableError` with the kinds and callable signatures listed in this contract.
- **B010** — the submitted package does not import forbidden upstream packages: email_validator, emailvalidator, dns.
<!-- featureliftbench:behavior-clauses:end -->
