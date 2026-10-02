from __future__ import annotations

from typing import Any


class DummyPool:
    """Minimal pool stand-in for ReadTimeoutError construction."""


DUMMY_POOL = DummyPool()


class MockResponse:
    """Minimal response object for Retry policy tests (no HTTP I/O)."""

    REDIRECT_STATUSES = (301, 302, 303, 307, 308)

    def __init__(
        self,
        status: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}

    def get_redirect_location(self) -> str | None | bool:
        if self.status in self.REDIRECT_STATUSES:
            return self.headers.get("location")
        return False
