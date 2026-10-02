# FeatureLift Task: WebSocket frame protocol

Extract a task-scoped subset of `wsproto` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    frame_protocol,
)
```

## Required API Details

- `frame_protocol` module must be importable
  - `frame_protocol.CloseReason(*values)` class constructor
  - `frame_protocol.FrameProtocol(client: 'bool', extensions: 'list[Extension]') -> 'None'` class constructor
    - `frame_protocol.FrameProtocol.close(self, code: 'int | None' = None, reason: 'str | None' = None) -> 'bytearray'`
    - `frame_protocol.FrameProtocol.receive_bytes(self, data: 'bytes') -> 'None'`
    - `frame_protocol.FrameProtocol.received_frames(self) -> 'Generator[Frame, None, None]'`
  - `frame_protocol.ParseFailed` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: parse and serialize text/binary WebSocket frames. Required observable cases include client receives unmasked text; binary frame extended payload length.
- The extracted feature must support this observable behavior: client/server masking rules and XOR payload decoding. Required observable cases include client receives unmasked text; client send data; server decodes masked client frame; role masking validation.
- The extracted feature must support this observable behavior: fragmented message reassembly across continuation frames. Required observable cases include fragmented message reassembly; reserved bit set on data frame.
- The extracted feature must support this observable behavior: ping/pong/close control frames with close codes. Required observable cases include close frame code and reason; close frame rejects one byte payload; reserved bit set on data frame.
- The package exposes the required task API paths `featurelifted.frame_protocol`, `featurelifted.frame_protocol.CloseReason`, `featurelifted.frame_protocol.FrameProtocol`, `featurelifted.frame_protocol.FrameProtocol.close`, `featurelifted.frame_protocol.FrameProtocol.receive_bytes`, `featurelifted.frame_protocol.FrameProtocol.received_frames`, `featurelifted.frame_protocol.ParseFailed` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `wsproto`.
- Do not implement HTTP/1.1 upgrade handshake (h11 integration).
- Do not implement WSConnection state machine and extensions negotiation I/O.
- Do not implement original wsproto import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse and serialize text/binary WebSocket frames. Required observable cases include client receives unmasked text; binary frame extended payload length.
- **B002** — The extracted feature must support this observable behavior: client/server masking rules and XOR payload decoding. Required observable cases include client receives unmasked text; client send data; server decodes masked client frame; role masking validation.
- **B003** — The extracted feature must support this observable behavior: fragmented message reassembly across continuation frames. Required observable cases include fragmented message reassembly; reserved bit set on data frame.
- **B004** — The extracted feature must support this observable behavior: ping/pong/close control frames with close codes. Required observable cases include close frame code and reason; close frame rejects one byte payload; reserved bit set on data frame.
- **B005** — The package exposes the required task API paths `featurelifted.frame_protocol`, `featurelifted.frame_protocol.CloseReason`, `featurelifted.frame_protocol.FrameProtocol`, `featurelifted.frame_protocol.FrameProtocol.close`, `featurelifted.frame_protocol.FrameProtocol.receive_bytes`, `featurelifted.frame_protocol.FrameProtocol.received_frames`, `featurelifted.frame_protocol.ParseFailed` with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: wsproto.
<!-- featureliftbench:behavior-clauses:end -->
