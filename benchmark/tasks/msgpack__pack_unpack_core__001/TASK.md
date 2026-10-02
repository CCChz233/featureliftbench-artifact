# FeatureLift Task: MessagePack pack/unpack core

Extract a task-scoped subset of `msgpack` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    dumps,
    ExtraData,
    ExtType,
    FormatError,
    loads,
    pack,
    packb,
    Packer,
    Timestamp,
    unpack,
    unpackb,
    Unpacker,
)
```

## Required API Details

- `packb(o, **kwargs)`
- `unpackb(packed, **kwargs)`
- `pack(o, stream, **kwargs)`
- `unpack(stream, **kwargs)`
- `dumps(o, **kwargs)`
- `loads(packed, **kwargs)`
- `Packer(*, default=None, use_single_float=False, autoreset=True, use_bin_type=True, strict_types=False, datetime=False, unicode_errors=None, buf_size=None)` class constructor
- `Unpacker(file_like=None, *, read_size=0, use_list=True, raw=False, timestamp=0, strict_map_key=True, object_hook=None, object_pairs_hook=None, list_hook=None, unicode_errors=None, max_buffer_size=104857600, ext_hook=<class 'ExtType'>, max_str_len=-1, max_bin_len=-1, max_array_len=-1, max_map_len=-1, max_ext_len=-1)` class constructor
- `ExtType(code, data)` class constructor
- `Timestamp(seconds, nanoseconds=0)` class constructor
- `ExtraData` must be importable and raisable
- `FormatError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: packb/unpackb roundtrip for nil, bool, int, float, str, bytes, list, tuple, dict. Required observable cases include pack unpack none bool int; pack unpack string and bytes; pack unpack list and dict; timestamp roundtrip; ext type roundtrip; strict map key allows int keys; extra data raises; ext hook transforms extension; format error on invalid bytes.
- The extracted feature must support this observable behavior: Packer options: use_bin_type, use_single_float, default hook, datetime timestamps. Required observable cases include unpack stream reads filelike.
- The extracted feature must support this observable behavior: Unpacker streaming feed/unpack, strict_map_key, raw/bin decoding, ext_hook. Required observable cases include packer unpacker streaming; strict map key allows int keys; ext hook transforms extension; unpack stream reads filelike.
- The extracted feature must support this observable behavior: Timestamp extension type pack/unpack (32/64/96-bit encodings). Required observable cases include pack unpack none bool int; pack unpack string and bytes; pack unpack list and dict; timestamp roundtrip.
- The extracted feature must support this observable behavior: ExtType custom extension payloads. Required observable cases include unpack stream reads filelike.
- The extracted feature must support this observable behavior: ExtraData, FormatError, StackError, OutOfData exception semantics. Required observable cases include unpack stream reads filelike.
- The package exposes the required task API paths `featurelifted.packb`, `featurelifted.unpackb`, `featurelifted.pack`, `featurelifted.unpack`, `featurelifted.dumps`, `featurelifted.loads`, `featurelifted.Packer`, `featurelifted.Unpacker`, `featurelifted.ExtType`, `featurelifted.Timestamp`, `featurelifted.ExtraData`, `featurelifted.FormatError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `msgpack`.
- Do not implement Cython _cmsgpack accelerated path and .pyx/.h build artifacts.
- Do not implement benchmark suite, docker images, docs, and upstream test harness.
- Do not implement original msgpack import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: packb/unpackb roundtrip for nil, bool, int, float, str, bytes, list, tuple, dict. Required observable cases include pack unpack none bool int; pack unpack string and bytes; pack unpack list and dict; timestamp roundtrip; ext type roundtrip; strict map key allows int keys; extra data raises; ext hook transforms extension; format error on invalid bytes.
- **B002** — The extracted feature must support this observable behavior: Packer options: use_bin_type, use_single_float, default hook, datetime timestamps. Required observable cases include unpack stream reads filelike.
- **B003** — The extracted feature must support this observable behavior: Unpacker streaming feed/unpack, strict_map_key, raw/bin decoding, ext_hook. Required observable cases include packer unpacker streaming; strict map key allows int keys; ext hook transforms extension; unpack stream reads filelike.
- **B004** — The extracted feature must support this observable behavior: Timestamp extension type pack/unpack (32/64/96-bit encodings). Required observable cases include pack unpack none bool int; pack unpack string and bytes; pack unpack list and dict; timestamp roundtrip.
- **B005** — The extracted feature must support this observable behavior: ExtType custom extension payloads. Required observable cases include unpack stream reads filelike.
- **B006** — The extracted feature must support this observable behavior: ExtraData, FormatError, StackError, OutOfData exception semantics. Required observable cases include unpack stream reads filelike.
- **B007** — The package exposes the required task API paths `featurelifted.packb`, `featurelifted.unpackb`, `featurelifted.pack`, `featurelifted.unpack`, `featurelifted.dumps`, `featurelifted.loads`, `featurelifted.Packer`, `featurelifted.Unpacker`, `featurelifted.ExtType`, `featurelifted.Timestamp`, `featurelifted.ExtraData`, `featurelifted.FormatError` with the kinds and callable signatures listed in this contract.
- **B008** — the submitted package does not import forbidden upstream packages: msgpack.
<!-- featureliftbench:behavior-clauses:end -->
