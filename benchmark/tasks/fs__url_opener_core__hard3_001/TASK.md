# FeatureLift Task: parse_fs_url FSOpenerRegistry

Extract a task-scoped subset of `fs` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    FSOpenerRegistry,
    InvalidPathError,
    normalize_fs_path,
    parse_fs_url,
    ParseError,
    UnsupportedProtocolError,
)
```

## Required API Details

- `parse_fs_url(fs_url: 'str') -> 'tuple[str, str | None, dict[str, str]]'`
- `FSOpenerRegistry(default_protocol: 'str' = 'osfs') -> 'None'` class constructor
  - `FSOpenerRegistry.open(self, fs_url: 'str') -> 'tuple[Any, str | None]'`
  - `FSOpenerRegistry.register(self, protocol: 'str', factory: 'Callable[[dict[str, str]], Any] | None' = None)`
- `ParseError` must be importable and raisable
- `UnsupportedProtocolError` must be importable and raisable
- `InvalidPathError` must be importable and raisable
- `normalize_fs_path(path: 'str | None') -> 'str | None'`

## Required Behavior

- `parse_fs_url` parses `scheme://resource!path` URLs and query parameters.
- `FSOpenerRegistry` registers opener factories and opens URLs.
- Invalid URLs raise ParseError; unknown schemes raise UnsupportedProtocolError; normalize_fs_path raises InvalidPathError when the path contains control characters.
- The package exposes the required task API paths `featurelifted.parse_fs_url`, `featurelifted.FSOpenerRegistry`, `featurelifted.FSOpenerRegistry.open`, `featurelifted.FSOpenerRegistry.register`, `featurelifted.ParseError`, `featurelifted.UnsupportedProtocolError`, `featurelifted.InvalidPathError`, `featurelifted.normalize_fs_path` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `fs`.
- Forbidden path access: `repo/, fs/`.
- Do not implement network access.
- Do not implement real filesystem backends.
- Do not implement OS mount operations.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — `parse_fs_url` parses `scheme://resource!path` URLs and query parameters.
- **B002** — `FSOpenerRegistry` registers opener factories and opens URLs.
- **B003** — Invalid URLs raise ParseError; unknown schemes raise UnsupportedProtocolError; normalize_fs_path raises InvalidPathError when the path contains control characters.
- **B004** — The package exposes the required task API paths `featurelifted.parse_fs_url`, `featurelifted.FSOpenerRegistry`, `featurelifted.FSOpenerRegistry.open`, `featurelifted.FSOpenerRegistry.register`, `featurelifted.ParseError`, `featurelifted.UnsupportedProtocolError`, `featurelifted.InvalidPathError`, `featurelifted.normalize_fs_path` with the kinds and callable signatures listed in this contract.
- **B005** — the submitted package does not import forbidden upstream packages: fs.
<!-- featureliftbench:behavior-clauses:end -->
