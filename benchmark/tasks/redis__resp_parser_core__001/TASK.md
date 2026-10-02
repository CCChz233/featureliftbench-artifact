# FeatureLift Task: RESP2/RESP3 wire parser

Extract a task-scoped subset of `redis` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    _parsers,
    exceptions,
)
```

## Required API Details

- `_parsers` module must be importable
  - `_parsers.Encoder(encoding, encoding_errors, decode_responses)` class constructor
    - `_parsers.Encoder.encode(self, value)`
  - `_parsers._RESP2Parser(socket_read_size)`
  - `_parsers._RESP3Parser(socket_read_size)`
- `exceptions` module must be importable
  - `exceptions.ResponseError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse RESP simple, bulk, and multi-bulk replies. Required observable cases include resp2 simple and bulk replies; resp2 array reply; resp2 error reply returns response error.
- The extracted feature must support this observable behavior: decode bulk strings with optional byte preservation. Required observable cases include resp3 null and boolean.
- The extracted feature must support this observable behavior: map Redis error prefixes to exception classes. Required observable cases include resp2 error reply returns response error.
- The extracted feature must support this observable behavior: encode commands to RESP bulk arrays. Required observable cases include resp2 array reply; encoder rejects bool.
- The extracted feature must support this observable behavior: buffer incremental socket reads via SocketBuffer. Required observable cases include resp3 null and boolean.
- The package exposes the required task API paths `featurelifted._parsers`, `featurelifted._parsers.Encoder`, `featurelifted._parsers.Encoder.encode`, `featurelifted._parsers._RESP2Parser`, `featurelifted._parsers._RESP3Parser`, `featurelifted.exceptions`, `featurelifted.exceptions.ResponseError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `redis`.
- Do not implement TCP/TLS connection management.
- Do not implement Redis command client and cluster logic.
- Do not implement pub/sub push notification handlers.
- Do not implement hiredis C extension parser.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse RESP simple, bulk, and multi-bulk replies. Required observable cases include resp2 simple and bulk replies; resp2 array reply; resp2 error reply returns response error.
- **B002** — The extracted feature must support this observable behavior: decode bulk strings with optional byte preservation. Required observable cases include resp3 null and boolean.
- **B003** — The extracted feature must support this observable behavior: map Redis error prefixes to exception classes. Required observable cases include resp2 error reply returns response error.
- **B004** — The extracted feature must support this observable behavior: encode commands to RESP bulk arrays. Required observable cases include resp2 array reply; encoder rejects bool.
- **B005** — The extracted feature must support this observable behavior: buffer incremental socket reads via SocketBuffer. Required observable cases include resp3 null and boolean.
- **B006** — The package exposes the required task API paths `featurelifted._parsers`, `featurelifted._parsers.Encoder`, `featurelifted._parsers.Encoder.encode`, `featurelifted._parsers._RESP2Parser`, `featurelifted._parsers._RESP3Parser`, `featurelifted.exceptions`, `featurelifted.exceptions.ResponseError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: redis.
<!-- featureliftbench:behavior-clauses:end -->
