from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import (
    ConnectTimeoutError,
    InvalidHeader,
    MaxRetryError,
    ReadTimeoutError,
    RequestHistory,
    ResponseError,
    Retry,
)
from conftest import DUMMY_POOL, MockResponse


def test_total_wins_over_connect() -> None:
    error = ConnectTimeoutError()
    retry = Retry(connect=3, total=2)
    retry = retry.increment(error=error)
    retry = retry.increment(error=error)
    with pytest.raises(MaxRetryError) as exc:
        retry.increment(error=error)
    assert exc.value.reason is error


def test_allowed_methods_and_status_forcelist_and() -> None:
    retry = Retry(status_forcelist=[500], allowed_methods=["POST"])
    assert not retry.is_retry("GET", status_code=500)
    assert retry.is_retry("POST", status_code=500)


def test_backoff_resets_after_redirect() -> None:
    retry = Retry(total=100, redirect=5, backoff_factor=0.2)
    retry = retry.increment(method="GET")
    retry = retry.increment(method="GET")
    assert retry.get_backoff_time() == 0.4
    redirect = MockResponse(status=302, headers={"location": "/next"})
    retry = retry.increment(method="GET", response=redirect)
    assert retry.get_backoff_time() == 0
    retry = retry.increment(method="GET")
    retry = retry.increment(method="GET")
    assert retry.get_backoff_time() == 0.4


def test_parse_retry_after_numeric_and_invalid() -> None:
    retry = Retry()
    assert retry.parse_retry_after("5") == 5.0
    with pytest.raises(InvalidHeader):
        retry.parse_retry_after("not-a-date")


def test_history_accumulates() -> None:
    error = ConnectTimeoutError()
    retry = Retry(total=10)
    retry = retry.increment("GET", "/a", None, error)
    assert retry.history == (RequestHistory("GET", "/a", error, None, None),)
    response = MockResponse(status=500)
    retry = retry.increment("GET", "/b", response, None)
    assert len(retry.history) == 2
    assert retry.history[-1].status == 500


def test_read_timeout_requires_allowed_method() -> None:
    error = ReadTimeoutError(DUMMY_POOL, "/", "read timed out")
    retry = Retry()
    with pytest.raises(ReadTimeoutError):
        retry.increment(method="POST", error=error)


def test_remove_headers_on_redirect_lowercased() -> None:
    retry = Retry(remove_headers_on_redirect=["Cookie", "Authorization"])
    assert retry.remove_headers_on_redirect == {"cookie", "authorization"}


def test_status_increment_raises_specific_error() -> None:
    retry = Retry(total=1)
    response = MockResponse(status=500)
    retry = retry.increment("POST", "/", response=response)
    msg = ResponseError.SPECIFIC_ERROR.format(status_code=500)
    with pytest.raises(MaxRetryError, match=re.escape(msg)):
        retry.increment("POST", "/", response=response)


def test_no_urllib3_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from urllib3|import urllib3)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
