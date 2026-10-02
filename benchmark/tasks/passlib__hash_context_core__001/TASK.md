# FeatureLift Task: CryptContext hash and verify

Extract a task-scoped subset of `passlib` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CryptContext,
)
```

## Required API Details

- `CryptContext(schemes=None, policy=<object object>, _autoload=True, **kwds)` class constructor
  - `CryptContext.hash(self, secret, scheme=None, category=None, **kwds)`
  - `CryptContext.identify(self, hash, category=None, resolve=False, required=False, unconfigured=False)`
  - `CryptContext.verify(self, secret, hash, scheme=None, category=None, **kwds)`

## Required Behavior

- The extracted feature must support this observable behavior: CryptContext hash and verify for pbkdf2_sha256. Required observable cases include hash and verify pbkdf2; context hash includes rounds; context verify and update roundtrip.
- The extracted feature must support this observable behavior: scheme options like default_rounds and deprecated schemes. Required observable cases include context verify and update roundtrip.
- The extracted feature must support this observable behavior: needs_update and identify handlers. Required observable cases include context verify and update roundtrip.
- The package exposes the required task API paths `featurelifted.CryptContext`, `featurelifted.CryptContext.hash`, `featurelifted.CryptContext.identify`, `featurelifted.CryptContext.verify` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `passlib`.
- Do not implement apache htpasswd helpers and TOTP.
- Do not implement django extension and host-specific handlers.
- Do not implement original passlib import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: CryptContext hash and verify for pbkdf2_sha256. Required observable cases include hash and verify pbkdf2; context hash includes rounds; context verify and update roundtrip.
- **B002** — The extracted feature must support this observable behavior: scheme options like default_rounds and deprecated schemes. Required observable cases include context verify and update roundtrip.
- **B003** — The extracted feature must support this observable behavior: needs_update and identify handlers. Required observable cases include context verify and update roundtrip.
- **B004** — The package exposes the required task API paths `featurelifted.CryptContext`, `featurelifted.CryptContext.hash`, `featurelifted.CryptContext.identify`, `featurelifted.CryptContext.verify` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: passlib.
<!-- featureliftbench:behavior-clauses:end -->
