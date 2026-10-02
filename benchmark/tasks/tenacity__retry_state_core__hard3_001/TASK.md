# FeatureLift Task: Retry state machine with stop/wait/retry predicates

Extract a task-scoped subset of `tenacity` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    retry_if_exception_type,
    retry_if_result,
    RetryCallState,
    RetryError,
    Retrying,
    stop_after_attempt,
    stop_after_delay,
    stop_before_delay,
    wait_chain,
    wait_combine,
    wait_exponential,
    wait_fixed,
    wait_none,
)
```

## Required API Details

- `Retrying(*, stop: 'StopBase | None' = None, wait: 'WaitBase | None' = None, retry: 'RetryBase | None' = None, sleep: 'Callable[[float], None] | None' = None, before_sleep: 'Callable[[RetryCallState], None] | None' = None, reraise: 'bool' = False, retry_error_cls: 'type[RetryError]' = <class 'RetryError'>, retry_error_callback: 'Callable[[RetryCallState], Any] | None' = None) -> 'None'` class constructor
- `RetryError` must be importable and raisable
- `retry_if_exception_type(exception_types: 'type[BaseException] | tuple[type[BaseException], ...]' = <class 'Exception'>) -> 'None'`
- `retry_if_result(predicate: 'Callable[[Any], bool]') -> 'None'`
- `stop_after_attempt(max_attempt_number: 'int') -> 'None'`
- `wait_fixed(wait: 'float') -> 'None'`
- `wait_chain(*strategies: 'WaitBase') -> 'None'`
- `wait_exponential(multiplier: 'float' = 1, max: 'float' = 3600.0, exp_base: 'float' = 2, min: 'float' = 0) -> 'None'`
- `RetryCallState(retry_object: "'Retrying'", fn: 'Callable[..., Any]', args: 'tuple[Any, ...]', kwargs: 'dict[str, Any]')` class constructor
- `stop_after_delay(max_delay: 'float') -> 'None'`
- `stop_before_delay(max_delay: 'float') -> 'None'`
- `wait_combine(*strategies: 'WaitBase') -> 'None'`
- `wait_none() -> 'None'`

## Required Behavior

- Retrying repeatedly calls the function while the retry predicate requests another attempt and stops when the function succeeds or a stop policy triggers.
- Track a `RetryCallState` with `attempt_number`, `outcome`, `idle_for`, `upcoming_sleep`, and `seconds_since_start`.
- When retries are exhausted, Retrying calls retry_error_callback if configured, reraises the final exception when requested, or raises RetryError.
- retry_if_exception_type retries matching exceptions and retry_if_result retries matching returned results.
- Retry predicates composed with | or & apply retry-any or retry-all semantics in operand order.
- stop_after_attempt, stop_after_delay, and stop_before_delay stop according to attempt count and elapsed or upcoming delay boundaries.
- wait_fixed, wait_none, wait_chain, wait_combine, and wait_exponential compute deterministic upcoming sleep durations; an empty wait_chain raises ValueError.
- before_sleep receives the updated retry state before idle_for is incremented, and retry_error_callback receives the exhausted state. At before_sleep, attempt_number is the attempt that just finished and has not yet been incremented for the next attempt.
- The package exposes the required task API paths `featurelifted.Retrying`, `featurelifted.RetryError`, `featurelifted.retry_if_exception_type`, `featurelifted.retry_if_result`, `featurelifted.stop_after_attempt`, `featurelifted.wait_fixed`, `featurelifted.wait_chain`, `featurelifted.wait_exponential`, `featurelifted.RetryCallState`, `featurelifted.stop_after_delay`, `featurelifted.stop_before_delay`, `featurelifted.wait_combine`, and 1 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `tenacity`.
- Forbidden path access: `repo/, tenacity/`.
- Do not implement network access.
- Do not implement original repository import at runtime.
- Do not implement source repo path access.
- Do not implement asyncio retrying.
- Do not implement tornado retrying.
- Do not implement decorator overloads.
- Do not implement logging callbacks.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — Retrying repeatedly calls the function while the retry predicate requests another attempt and stops when the function succeeds or a stop policy triggers.
- **B002** — Track a `RetryCallState` with `attempt_number`, `outcome`, `idle_for`, `upcoming_sleep`, and `seconds_since_start`.
- **B003** — When retries are exhausted, Retrying calls retry_error_callback if configured, reraises the final exception when requested, or raises RetryError.
- **B004** — retry_if_exception_type retries matching exceptions and retry_if_result retries matching returned results.
- **B005** — Retry predicates composed with | or & apply retry-any or retry-all semantics in operand order.
- **B006** — stop_after_attempt, stop_after_delay, and stop_before_delay stop according to attempt count and elapsed or upcoming delay boundaries.
- **B007** — wait_fixed, wait_none, wait_chain, wait_combine, and wait_exponential compute deterministic upcoming sleep durations; an empty wait_chain raises ValueError.
- **B008** — before_sleep receives the updated retry state before idle_for is incremented, and retry_error_callback receives the exhausted state. At before_sleep, attempt_number is the attempt that just finished and has not yet been incremented for the next attempt.
- **B009** — The package exposes the required task API paths `featurelifted.Retrying`, `featurelifted.RetryError`, `featurelifted.retry_if_exception_type`, `featurelifted.retry_if_result`, `featurelifted.stop_after_attempt`, `featurelifted.wait_fixed`, `featurelifted.wait_chain`, `featurelifted.wait_exponential`, `featurelifted.RetryCallState`, `featurelifted.stop_after_delay`, `featurelifted.stop_before_delay`, `featurelifted.wait_combine`, and 1 listed members with the kinds and callable signatures listed in this contract.
- **B010** — the submitted package does not import forbidden upstream packages: tenacity.
<!-- featureliftbench:behavior-clauses:end -->
