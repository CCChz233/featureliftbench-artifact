# FeatureLift Task: Timed URL-safe serializer

Extract a task-scoped subset of `itsdangerous` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)
```

## Required API Details

- `URLSafeTimedSerializer(secret_key, salt='featurelift', *, now=None)` class constructor
  - `URLSafeTimedSerializer.dumps(self, obj)`
  - `URLSafeTimedSerializer.loads(self, token, max_age=None, now=None)`
- `BadSignature` must be importable and raisable
- `SignatureExpired` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: deterministic URL-safe dumps and loads for JSON-compatible values. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- The extracted feature must support this observable behavior: salt-separated HMAC-SHA256 signatures. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- The extracted feature must support this observable behavior: timestamp max_age validation with injectable current time. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- The extracted feature must support this observable behavior: BadSignature and SignatureExpired error distinctions. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- The package exposes the required task API paths `featurelifted.URLSafeTimedSerializer`, `featurelifted.URLSafeTimedSerializer.dumps`, `featurelifted.URLSafeTimedSerializer.loads`, `featurelifted.BadSignature`, `featurelifted.SignatureExpired` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `itsdangerous`.
- Forbidden path access: `repo/, itsdangerous/`.
- Do not implement JWS.
- Do not implement fallback signers.
- Do not implement non-JSON serializers.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: deterministic URL-safe dumps and loads for JSON-compatible values. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- **B002** — The extracted feature must support this observable behavior: salt-separated HMAC-SHA256 signatures. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- **B003** — The extracted feature must support this observable behavior: timestamp max_age validation with injectable current time. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- **B004** — The extracted feature must support this observable behavior: BadSignature and SignatureExpired error distinctions. Required observable cases include roundtrip and salt separation; tampering raises bad signature; expiry boundary and error type; wrong key and malformed token.
- **B005** — The package exposes the required task API paths `featurelifted.URLSafeTimedSerializer`, `featurelifted.URLSafeTimedSerializer.dumps`, `featurelifted.URLSafeTimedSerializer.loads`, `featurelifted.BadSignature`, `featurelifted.SignatureExpired` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: itsdangerous.
<!-- featureliftbench:behavior-clauses:end -->
