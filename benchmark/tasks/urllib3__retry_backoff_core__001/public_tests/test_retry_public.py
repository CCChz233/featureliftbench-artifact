from __future__ import annotations

import pytest

from featurelifted import ConnectTimeoutError, MaxRetryError, Retry


def test_retry_defaults_and_from_int() -> None:
    retry = Retry()
    assert retry.total == 10
    assert Retry.from_int(3).total == 3
    assert Retry.from_int(False).total is False


def test_is_retry_status_forcelist() -> None:
    retry = Retry(status_forcelist=range(500, 600))
    assert not retry.is_retry("GET", status_code=200)
    assert retry.is_retry("GET", status_code=503)


def test_backoff_progression() -> None:
    retry = Retry(total=100, backoff_factor=0.2)
    assert retry.get_backoff_time() == 0
    retry = retry.increment(method="GET")
    retry = retry.increment(method="GET")
    assert retry.get_backoff_time() == 0.4


def test_connect_timeout_increment() -> None:
    error = ConnectTimeoutError()
    retry = Retry(connect=1)
    retry = retry.increment(error=error)
    with pytest.raises(MaxRetryError):
        retry.increment(error=error)
