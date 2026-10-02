# FeatureLift Task: WebSocket HTTP upgrade handshake parsing

Extract a task-scoped subset of `websockets` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    accept_key,
    exceptions,
    generate_key,
    Headers,
    headers,
    http11,
    Request,
    Response,
    streams,
    validate_handshake_request,
)
```

## Required API Details

- `Headers(*args: 'HeadersLike', **kwargs: 'str') -> 'None'` class constructor
  - `Headers.get_all(self, key: 'str') -> 'list[str]'`
  - `Headers.__getitem__(self, key: 'str') -> 'str'`
- `Request(path: 'str', headers: 'Headers', _exception: 'Exception | None' = None) -> None` class constructor
  - `Request.parse(read_line: 'Callable[[int], Generator[None, None, bytes | bytearray]]') -> 'Generator[None, None, Request]'`
- `Response(status_code: 'int', reason_phrase: 'str', headers: 'Headers', body: 'bytes | bytearray' = b'', _exception: 'Exception | None' = None) -> None` class constructor
- `accept_key(key: 'str') -> 'str'`
- `generate_key() -> 'str'`
- `validate_handshake_request(request: 'Request', *, origins: 'Sequence[Origin | re.Pattern[str] | None] | None' = None) -> 'str'`
- `exceptions` module must be importable
  - `exceptions.InvalidHeader` must be importable and raisable
  - `exceptions.InvalidHeaderFormat` must be importable and raisable
  - `exceptions.InvalidHeaderValue` must be importable and raisable
  - `exceptions.InvalidOrigin` must be importable and raisable
  - `exceptions.InvalidUpgrade` must be importable and raisable
  - `exceptions.SecurityError` must be importable and raisable
- `headers` module must be importable
  - `headers.build_authorization_basic(username: 'str', password: 'str') -> 'str'`
  - `headers.build_subprotocol(subprotocols: 'Sequence[Subprotocol]') -> 'str'`
  - `headers.build_www_authenticate_basic(realm: 'str') -> 'str'`
  - `headers.parse_authorization_basic(header: 'str') -> 'tuple[str, str]'`
  - `headers.parse_connection(header: 'str') -> 'list[ConnectionOption]'`
  - `headers.parse_extension(header: 'str') -> 'list[ExtensionHeader]'`
  - `headers.parse_subprotocol(header: 'str') -> 'list[Subprotocol]'`
  - `headers.parse_upgrade(header: 'str') -> 'list[UpgradeProtocol]'`
  - `headers.validate_subprotocols(subprotocols: 'Sequence[Subprotocol]') -> 'None'`
- `http11` module must be importable
  - `http11.parse_headers(read_line: 'Callable[[int], Generator[None, None, bytes | bytearray]]') -> 'Generator[None, None, Headers]'`
- `streams` module must be importable
  - `streams.StreamReader() -> 'None'` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: parse Connection and Upgrade header lists with OWS and empty elements. Required observable cases include parse connection and upgrade; parse upgrade case insensitive list; headers multiple connection values.
- The extracted feature must support this observable behavior: parse Sec-WebSocket-Extensions and Sec-WebSocket-Protocol grammars. Required observable cases include parse extension with quoted params; parse subprotocol skips empty elements; parse extension invalid quoted token; build subprotocol roundtrip; validate subprotocols rejects invalid token.
- The extracted feature must support this observable behavior: parse WebSocket handshake HTTP requests from byte streams. Required observable cases include parse websocket request basic; parse request invalid method; parse headers security limit.
- The extracted feature must support this observable behavior: case-insensitive Headers lookup with multiple values per name. Required observable cases include headers case insensitive lookup; headers multiple connection values.
- The extracted feature must support this observable behavior: validate handshake request headers including Sec-WebSocket-Key and Version. Required observable cases include validate handshake rejects bad upgrade; validate handshake missing key; validate handshake invalid key length; validate handshake origin allowlist; validate handshake origin regex allowlist.
- The extracted feature must support this observable behavior: compute Sec-WebSocket-Accept from Sec-WebSocket-Key. Required observable cases include accept key rfc6455 example; validate subprotocols rejects invalid token.
- The extracted feature must support this observable behavior: raise typed errors for malformed headers and upgrade requests. Required observable cases include validate handshake rejects bad upgrade; parse request invalid method; parse headers security limit; parse extension invalid quoted token; validate subprotocols rejects invalid token.
- The package exposes the required task API paths `featurelifted.Headers`, `featurelifted.Headers.get_all`, `featurelifted.Headers.__getitem__`, `featurelifted.Request`, `featurelifted.Request.parse`, `featurelifted.Response`, `featurelifted.accept_key`, `featurelifted.generate_key`, `featurelifted.validate_handshake_request`, `featurelifted.exceptions`, `featurelifted.exceptions.InvalidHeader`, `featurelifted.exceptions.InvalidHeaderFormat`, and 18 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `websockets`.
- Do not implement socket and asyncio/sync network I/O.
- Do not implement WebSocket frame encoding and masking.
- Do not implement ServerProtocol and ClientProtocol connection state machines.
- Do not implement extensions negotiation with permessage-deflate implementations.
- Do not implement CLI, docs, CI, and original tests.
- Do not implement original websockets package import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse Connection and Upgrade header lists with OWS and empty elements. Required observable cases include parse connection and upgrade; parse upgrade case insensitive list; headers multiple connection values.
- **B002** — The extracted feature must support this observable behavior: parse Sec-WebSocket-Extensions and Sec-WebSocket-Protocol grammars. Required observable cases include parse extension with quoted params; parse subprotocol skips empty elements; parse extension invalid quoted token; build subprotocol roundtrip; validate subprotocols rejects invalid token.
- **B003** — The extracted feature must support this observable behavior: parse WebSocket handshake HTTP requests from byte streams. Required observable cases include parse websocket request basic; parse request invalid method; parse headers security limit.
- **B004** — The extracted feature must support this observable behavior: case-insensitive Headers lookup with multiple values per name. Required observable cases include headers case insensitive lookup; headers multiple connection values.
- **B005** — The extracted feature must support this observable behavior: validate handshake request headers including Sec-WebSocket-Key and Version. Required observable cases include validate handshake rejects bad upgrade; validate handshake missing key; validate handshake invalid key length; validate handshake origin allowlist; validate handshake origin regex allowlist.
- **B006** — The extracted feature must support this observable behavior: compute Sec-WebSocket-Accept from Sec-WebSocket-Key. Required observable cases include accept key rfc6455 example; validate subprotocols rejects invalid token.
- **B007** — The extracted feature must support this observable behavior: raise typed errors for malformed headers and upgrade requests. Required observable cases include validate handshake rejects bad upgrade; parse request invalid method; parse headers security limit; parse extension invalid quoted token; validate subprotocols rejects invalid token.
- **B008** — The package exposes the required task API paths `featurelifted.Headers`, `featurelifted.Headers.get_all`, `featurelifted.Headers.__getitem__`, `featurelifted.Request`, `featurelifted.Request.parse`, `featurelifted.Response`, `featurelifted.accept_key`, `featurelifted.generate_key`, `featurelifted.validate_handshake_request`, `featurelifted.exceptions`, `featurelifted.exceptions.InvalidHeader`, `featurelifted.exceptions.InvalidHeaderFormat`, and 18 listed members with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: websockets.
<!-- featureliftbench:behavior-clauses:end -->
