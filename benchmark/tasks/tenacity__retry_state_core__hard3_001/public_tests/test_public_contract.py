import pytest

from featurelifted import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_fixed,
)


def test_retry_exception_until_success_without_real_sleep():
    calls = []
    sleeps = []

    def flaky():
        calls.append("call")
        if len(calls) < 3:
            raise ValueError("not yet")
        return "ok"

    retrying = Retrying(
        stop=stop_after_attempt(5),
        wait=wait_fixed(0.25),
        retry=retry_if_exception_type(ValueError),
        sleep=sleeps.append,
    )

    assert retrying(flaky) == "ok"
    assert len(calls) == 3
    assert sleeps == [0.25, 0.25]


def test_retry_result_predicate():
    values = iter(["pending", "pending", "done"])
    retrying = Retrying(
        stop=stop_after_attempt(4),
        wait=wait_fixed(0),
        retry=retry_if_result(lambda value: value == "pending"),
        sleep=lambda seconds: None,
    )

    assert retrying(lambda: next(values)) == "done"


def test_retry_error_when_stop_is_reached():
    retrying = Retrying(
        stop=stop_after_attempt(2),
        wait=wait_fixed(0),
        retry=retry_if_exception_type(RuntimeError),
        sleep=lambda seconds: None,
    )

    with pytest.raises(RetryError) as err:
        retrying(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert err.value.last_attempt.attempt_number == 2
    assert isinstance(err.value.last_attempt.exception(), RuntimeError)
