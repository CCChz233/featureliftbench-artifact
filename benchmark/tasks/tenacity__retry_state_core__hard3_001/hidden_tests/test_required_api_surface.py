"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Retrying,
    RetryError,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_fixed,
    wait_chain,
    wait_exponential,
    RetryCallState,
    stop_after_delay,
    stop_before_delay,
    wait_combine,
    wait_none,
)


def test_required_api_surface():
    assert isinstance(Retrying, type)
    assert issubclass(RetryError, BaseException)
    assert callable(retry_if_exception_type)
    assert callable(retry_if_result)
    assert callable(stop_after_attempt)
    assert callable(wait_fixed)
    assert callable(wait_chain)
    assert callable(wait_exponential)
    assert isinstance(RetryCallState, type)
    assert callable(stop_after_delay)
    assert callable(stop_before_delay)
    assert callable(wait_combine)
    assert callable(wait_none)
