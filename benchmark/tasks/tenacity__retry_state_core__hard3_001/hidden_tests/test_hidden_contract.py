import pytest

from featurelifted import (
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_chain,
    wait_exponential,
    wait_fixed,
)


def test_wait_chain_requires_at_least_one_strategy():
    with pytest.raises(ValueError, match="at least one"):
        wait_chain()


def test_wait_chain_uses_last_strategy_after_exhaustion():
    sleeps = []
    calls = []

    def always_bad():
        calls.append(None)
        raise LookupError("again")

    retrying = Retrying(
        stop=stop_after_attempt(4),
        wait=wait_chain(wait_fixed(1), wait_fixed(2)),
        retry=retry_if_exception_type(LookupError),
        sleep=sleeps.append,
        retry_error_callback=lambda state: state.attempt_number,
    )

    assert retrying(always_bad) == 4
    assert sleeps == [1.0, 2.0, 2.0]
    assert len(calls) == 4


def test_before_sleep_observes_retry_state():
    snapshots = []

    def callback(state):
        snapshots.append(
            {
                "attempt": state.attempt_number,
                "sleep": state.upcoming_sleep,
                "failed": state.outcome.failed,
                "idle": state.idle_for,
            }
        )

    values = iter([None, None, "ok"])
    retrying = Retrying(
        stop=stop_after_attempt(5),
        wait=wait_fixed(0.5),
        retry=retry_if_result(lambda value: value is None),
        before_sleep=callback,
        sleep=lambda seconds: None,
    )

    assert retrying(lambda: next(values)) == "ok"
    assert snapshots == [
        {"attempt": 1, "sleep": 0.5, "failed": False, "idle": 0.0},
        {"attempt": 2, "sleep": 0.5, "failed": False, "idle": 0.5},
    ]


def test_reraise_surfaces_last_exception():
    retrying = Retrying(
        stop=stop_after_attempt(1),
        wait=wait_fixed(0),
        retry=retry_if_exception_type(KeyError),
        sleep=lambda seconds: None,
        reraise=True,
    )

    with pytest.raises(KeyError, match="missing"):
        retrying(lambda: (_ for _ in ()).throw(KeyError("missing")))


def test_strategy_composition_and_exponential_wait():
    sleeps = []
    values = iter([ValueError("bad"), "retry-me", "ok"])

    def action():
        value = next(values)
        if isinstance(value, BaseException):
            raise value
        return value

    retrying = Retrying(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, max=5),
        retry=retry_if_exception_type(ValueError) | retry_if_result(lambda value: value == "retry-me"),
        sleep=sleeps.append,
    )

    assert retrying(action) == "ok"
    assert sleeps == [0.5, 1.0]
