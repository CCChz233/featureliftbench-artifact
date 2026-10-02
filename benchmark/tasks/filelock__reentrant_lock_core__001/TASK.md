# FeatureLift Task: Reentrant filesystem lock

Extract a task-scoped subset of `filelock` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    FileLock,
    Timeout,
)
```

## Required API Details

- `FileLock(lock_file, timeout=-1, poll_interval=0.05)` class constructor
  - `FileLock.acquire(self, timeout=None, poll_interval=None, blocking=True)`
  - `FileLock.is_locked` attribute must exist on instances
  - `FileLock.release(self, force=False)`
- `Timeout` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: exclusive lock-file acquisition across instances. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- The extracted feature must support this observable behavior: reentrant acquire and balanced release on one instance. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- The extracted feature must support this observable behavior: timeout and non-blocking acquisition. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- The extracted feature must support this observable behavior: context-manager release and lock-file cleanup. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- The package exposes the required task API paths `featurelifted.FileLock`, `featurelifted.FileLock.acquire`, `featurelifted.FileLock.is_locked`, `featurelifted.FileLock.release`, `featurelifted.Timeout` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `filelock`.
- Forbidden path access: `repo/, filelock/`.
- Do not implement Windows msvcrt backend.
- Do not implement async locks.
- Do not implement soft-lock fallback.
- Do not implement original repository import at runtime.
- Do not implement source repository path access.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: exclusive lock-file acquisition across instances. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- **B002** — The extracted feature must support this observable behavior: reentrant acquire and balanced release on one instance. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- **B003** — The extracted feature must support this observable behavior: timeout and non-blocking acquisition. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- **B004** — The extracted feature must support this observable behavior: context-manager release and lock-file cleanup. Required observable cases include context and reentrant release; nonblocking contention; force release and idempotence; two instances can acquire sequentially.
- **B005** — The package exposes the required task API paths `featurelifted.FileLock`, `featurelifted.FileLock.acquire`, `featurelifted.FileLock.is_locked`, `featurelifted.FileLock.release`, `featurelifted.Timeout` with the kinds and callable signatures listed in this contract.
- **B006** — The submitted package does not import forbidden upstream packages: filelock.
<!-- featureliftbench:behavior-clauses:end -->
