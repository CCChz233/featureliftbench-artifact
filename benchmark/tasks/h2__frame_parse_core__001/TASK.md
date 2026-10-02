# FeatureLift Task: HTTP/2 frame parse and buffer

Extract a task-scoped subset of `h2` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    h2,
    hyperframe,
)
```

## Required API Details

- `h2.exceptions` module must be importable
  - `h2.exceptions.FrameTooLargeError` must be importable and raisable
  - `h2.exceptions.ProtocolError` must be importable and raisable
- `h2.frame_buffer` module must be importable
  - `h2.frame_buffer.FrameBuffer(server: 'bool' = False) -> 'None'` class constructor
    - `h2.frame_buffer.FrameBuffer.add_data(self, data: 'bytes') -> 'None'`
    - `h2.frame_buffer.FrameBuffer.max_frame_size` attribute must exist on instances
- `hyperframe.exceptions` module must be importable
  - `hyperframe.exceptions.InvalidDataError` must be importable and raisable
- `hyperframe.frame` module must be importable
  - `hyperframe.frame.ContinuationFrame(stream_id: 'int', data: 'bytes' = b'', **kwargs: 'Any') -> 'None'` class constructor
    - `hyperframe.frame.ContinuationFrame.data` attribute must exist on instances
    - `hyperframe.frame.ContinuationFrame.flags` attribute must exist on instances
    - `hyperframe.frame.ContinuationFrame.serialize(self) -> 'bytes'`
  - `hyperframe.frame.DataFrame(stream_id: 'int', data: 'bytes' = b'', **kwargs: 'Any') -> 'None'` class constructor
    - `hyperframe.frame.DataFrame.data` attribute must exist on instances
    - `hyperframe.frame.DataFrame.serialize(self) -> 'bytes'`
  - `hyperframe.frame.Frame(stream_id: 'int', flags: 'Iterable[str]' = ()) -> 'None'` class constructor
  - `hyperframe.frame.HeadersFrame(stream_id: 'int', data: 'bytes' = b'', **kwargs: 'Any') -> 'None'` class constructor
    - `hyperframe.frame.HeadersFrame.data` attribute must exist on instances
    - `hyperframe.frame.HeadersFrame.serialize(self) -> 'bytes'`
  - `hyperframe.frame.PingFrame(stream_id: 'int' = 0, opaque_data: 'bytes' = b'', **kwargs: 'Any') -> 'None'` class constructor

## Required Behavior

- The extracted feature must support this observable behavior: parse and serialize HTTP/2 frames (DATA, HEADERS, PING, SETTINGS, etc.). Required observable cases include ping frame roundtrip; data frame via frame buffer; ping stream id must be zero; frame buffer rejects bad preamble; frame buffer enforces max frame size.
- The extracted feature must support this observable behavior: FrameBuffer incremental parsing with continuation reassembly. Required observable cases include continuation reassembly.
- The extracted feature must support this observable behavior: HTTP/2 connection preamble validation for server mode. Required observable cases include frame buffer rejects bad preamble.
- The extracted feature must support this observable behavior: frame size limits and typed protocol errors. Required observable cases include frame buffer enforces max frame size.
- The package exposes the required task API paths `featurelifted.h2.exceptions`, `featurelifted.h2.exceptions.FrameTooLargeError`, `featurelifted.h2.exceptions.ProtocolError`, `featurelifted.h2.frame_buffer`, `featurelifted.h2.frame_buffer.FrameBuffer`, `featurelifted.h2.frame_buffer.FrameBuffer.add_data`, `featurelifted.h2.frame_buffer.FrameBuffer.max_frame_size`, `featurelifted.hyperframe.exceptions`, `featurelifted.hyperframe.exceptions.InvalidDataError`, `featurelifted.hyperframe.frame`, `featurelifted.hyperframe.frame.ContinuationFrame`, `featurelifted.hyperframe.frame.ContinuationFrame.data`, and 10 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `h2, hyperframe`.
- Do not implement h2 connection and stream state machines.
- Do not implement HPACK header compression and flow control windows.
- Do not implement network sockets and asyncio integration.
- Do not implement original h2 or hyperframe imports at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse and serialize HTTP/2 frames (DATA, HEADERS, PING, SETTINGS, etc.). Required observable cases include ping frame roundtrip; data frame via frame buffer; ping stream id must be zero; frame buffer rejects bad preamble; frame buffer enforces max frame size.
- **B002** — The extracted feature must support this observable behavior: FrameBuffer incremental parsing with continuation reassembly. Required observable cases include continuation reassembly.
- **B003** — The extracted feature must support this observable behavior: HTTP/2 connection preamble validation for server mode. Required observable cases include frame buffer rejects bad preamble.
- **B004** — The extracted feature must support this observable behavior: frame size limits and typed protocol errors. Required observable cases include frame buffer enforces max frame size.
- **B005** — The package exposes the required task API paths `featurelifted.h2.exceptions`, `featurelifted.h2.exceptions.FrameTooLargeError`, `featurelifted.h2.exceptions.ProtocolError`, `featurelifted.h2.frame_buffer`, `featurelifted.h2.frame_buffer.FrameBuffer`, `featurelifted.h2.frame_buffer.FrameBuffer.add_data`, `featurelifted.h2.frame_buffer.FrameBuffer.max_frame_size`, `featurelifted.hyperframe.exceptions`, `featurelifted.hyperframe.exceptions.InvalidDataError`, `featurelifted.hyperframe.frame`, `featurelifted.hyperframe.frame.ContinuationFrame`, `featurelifted.hyperframe.frame.ContinuationFrame.data`, and 10 listed members with the kinds and callable signatures listed in this contract.
- **B006** — the submitted package does not import forbidden upstream packages: h2, hyperframe.
<!-- featureliftbench:behavior-clauses:end -->
