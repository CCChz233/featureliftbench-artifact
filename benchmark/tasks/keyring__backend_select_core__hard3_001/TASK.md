# FeatureLift Task: Backend discovery, priority sorting, and failover selection

Extract a task-scoped subset of `keyring` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    Backend,
    BackendNotFound,
    ChainerBackend,
    Credential,
    ErrorBackend,
    FailBackend,
    MemoryBackend,
    PasswordDeleteError,
    PasswordSetError,
    select_backend,
)
```

## Required API Details

- `ChainerBackend(backends: 'list[Backend] | tuple[Backend, ...]') -> 'None'` class constructor
  - `ChainerBackend.get_password(self, service: 'str', username: 'str') -> 'str | None'`
  - `ChainerBackend.set_password(self, service: 'str', username: 'str', password: 'str') -> 'None'`
- `MemoryBackend(label: 'str', priority: 'float' = 1.0, data: 'dict[tuple[str, str], str]' = <factory>) -> None` class constructor
  - `MemoryBackend.get_credential(self, service: 'str', username: 'str | None' = None) -> 'Credential | None'`
  - `MemoryBackend.get_password(self, service: 'str', username: 'str') -> 'str | None'`
  - `MemoryBackend.set_password(self, service: 'str', username: 'str', password: 'str') -> 'None'`
- `select_backend(backends: 'list[Any] | tuple[Any, ...]', env: 'dict[str, str] | None' = None) -> 'Backend'`
- `Backend()` class constructor
- `BackendNotFound` must be importable and raisable
- `Credential(username: 'str', password: 'str') -> None` class constructor
- `ErrorBackend(label: 'str' = 'error', priority: 'float' = 1.0, error: 'Exception' = <factory>) -> None` class constructor
- `FailBackend()` class constructor
- `PasswordDeleteError` must be importable and raisable
- `PasswordSetError` must be importable and raisable

## Required Behavior

- Backend implementations expose priority and the declared password and credential operations used by selection and chaining.
- MemoryBackend stores deterministic credentials and can discover a stored username when get_credential is called without one.
- When no viable backend exists, selection returns FailBackend and its password operations fail through the declared error API.
- ErrorBackend raises its configured failure so ChainerBackend fallback paths can be observed.
- ChainerBackend sorts viable backends by descending priority, skips backend failures, and returns the first successful password result.
- select_backend chooses the highest-priority non-negative viable backend and falls back to FailBackend when none qualifies.
- When PYTHON_KEYRING_BACKEND is provided, select_backend matches the requested backend name or class and raises BackendNotFound if it is unavailable.
- Credential values and password set/delete failures use the declared Credential, PasswordSetError, and PasswordDeleteError types.
- The package exposes the required task API paths `featurelifted.ChainerBackend`, `featurelifted.ChainerBackend.get_password`, `featurelifted.ChainerBackend.set_password`, `featurelifted.MemoryBackend`, `featurelifted.MemoryBackend.get_credential`, `featurelifted.MemoryBackend.get_password`, `featurelifted.MemoryBackend.set_password`, `featurelifted.select_backend`, `featurelifted.Backend`, `featurelifted.BackendNotFound`, `featurelifted.Credential`, `featurelifted.ErrorBackend`, and 3 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `keyring`.
- Forbidden path access: `repo/, keyring/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement macOS Keychain.
- Do not implement Windows credential vault.
- Do not implement SecretService.
- Do not implement KWallet.
- Do not implement CLI and config file writes.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — Backend implementations expose priority and the declared password and credential operations used by selection and chaining.
- **B002** — MemoryBackend stores deterministic credentials and can discover a stored username when get_credential is called without one.
- **B003** — When no viable backend exists, selection returns FailBackend and its password operations fail through the declared error API.
- **B004** — ErrorBackend raises its configured failure so ChainerBackend fallback paths can be observed.
- **B005** — ChainerBackend sorts viable backends by descending priority, skips backend failures, and returns the first successful password result.
- **B006** — select_backend chooses the highest-priority non-negative viable backend and falls back to FailBackend when none qualifies.
- **B007** — When PYTHON_KEYRING_BACKEND is provided, select_backend matches the requested backend name or class and raises BackendNotFound if it is unavailable.
- **B008** — Credential values and password set/delete failures use the declared Credential, PasswordSetError, and PasswordDeleteError types.
- **B009** — The package exposes the required task API paths `featurelifted.ChainerBackend`, `featurelifted.ChainerBackend.get_password`, `featurelifted.ChainerBackend.set_password`, `featurelifted.MemoryBackend`, `featurelifted.MemoryBackend.get_credential`, `featurelifted.MemoryBackend.get_password`, `featurelifted.MemoryBackend.set_password`, `featurelifted.select_backend`, `featurelifted.Backend`, `featurelifted.BackendNotFound`, `featurelifted.Credential`, `featurelifted.ErrorBackend`, and 3 listed members with the kinds and callable signatures listed in this contract.
- **B010** — the submitted package does not import forbidden upstream packages: keyring.
<!-- featureliftbench:behavior-clauses:end -->
