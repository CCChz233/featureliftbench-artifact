# FeatureLift Task: HTTP/1.1 message parse and state machine

Extract a task-scoped subset of `h11` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    CLIENT,
    Connection,
    Data,
    EndOfMessage,
    NEED_DATA,
    RemoteProtocolError,
    Request,
    Response,
    SERVER,
)
```

## Required API Details

- `Connection(our_role: Type[Sentinel], max_incomplete_event_size: int = 16384) -> None` class constructor
  - `Connection.next_event(self) -> Union[Event, Type[NEED_DATA], Type[PAUSED]]`
  - `Connection.receive_data(self, data: bytes) -> None`
- `CLIENT(name: str, bases: Tuple[type, ...], namespace: Dict[str, Any], **kwds: Any) -> ~_T_Sentinel` class constructor
- `SERVER(name: str, bases: Tuple[type, ...], namespace: Dict[str, Any], **kwds: Any) -> ~_T_Sentinel` class constructor
- `Request(*, method: Union[bytes, str], headers: Union[Headers, List[Tuple[bytes, bytes]], List[Tuple[str, str]]], target: Union[bytes, str], http_version: Union[bytes, str] = b'1.1', _parsed: bool = False) -> None` class constructor
- `Response(*, headers: Union[Headers, List[Tuple[bytes, bytes]], List[Tuple[str, str]]], status_code: int, http_version: Union[bytes, str] = b'1.1', reason: Union[bytes, str] = b'', _parsed: bool = False) -> None` class constructor
- `Data(data: bytes, chunk_start: bool = False, chunk_end: bool = False) -> None` class constructor
- `EndOfMessage(*, headers: Union[Headers, List[Tuple[bytes, bytes]], List[Tuple[str, str]], NoneType] = None, _parsed: bool = False) -> None` class constructor
- `NEED_DATA(name: str, bases: Tuple[type, ...], namespace: Dict[str, Any], **kwds: Any) -> ~_T_Sentinel` class constructor
- `RemoteProtocolError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse request and response start-lines and headers. Required observable cases include parse simple http request; client request serialization; malformed request raises.
- The extracted feature must support this observable behavior: frame bodies with content-length and chunked encoding. Required observable cases include chunked response body.
- The extracted feature must support this observable behavior: drive client/server role state transitions. Required observable cases include client request serialization; malformed request raises.
- The extracted feature must support this observable behavior: surface protocol errors for malformed messages. Required observable cases include malformed request raises.
- The extracted feature must support this observable behavior: serialize events back to wire bytes. Required observable cases include malformed request raises.
- The package exposes the required task API paths `featurelifted.Connection`, `featurelifted.Connection.next_event`, `featurelifted.Connection.receive_data`, `featurelifted.CLIENT`, `featurelifted.SERVER`, `featurelifted.Request`, `featurelifted.Response`, `featurelifted.Data`, `featurelifted.EndOfMessage`, `featurelifted.NEED_DATA`, `featurelifted.RemoteProtocolError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `h11`.
- Do not implement socket I/O and TLS.
- Do not implement HTTP/2 or WebSocket upgrades beyond state flags.
- Do not implement original project tests.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse request and response start-lines and headers. Required observable cases include parse simple http request; client request serialization; malformed request raises.
- **B002** — The extracted feature must support this observable behavior: frame bodies with content-length and chunked encoding. Required observable cases include chunked response body.
- **B003** — The extracted feature must support this observable behavior: drive client/server role state transitions. Required observable cases include client request serialization; malformed request raises.
- **B004** — The extracted feature must support this observable behavior: surface protocol errors for malformed messages. Required observable cases include malformed request raises.
- **B005** — The extracted feature must support this observable behavior: serialize events back to wire bytes. Required observable cases include malformed request raises.
- **B006** — The package exposes the required task API paths `featurelifted.Connection`, `featurelifted.Connection.next_event`, `featurelifted.Connection.receive_data`, `featurelifted.CLIENT`, `featurelifted.SERVER`, `featurelifted.Request`, `featurelifted.Response`, `featurelifted.Data`, `featurelifted.EndOfMessage`, `featurelifted.NEED_DATA`, `featurelifted.RemoteProtocolError` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: h11.
<!-- featureliftbench:behavior-clauses:end -->
