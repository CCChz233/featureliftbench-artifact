from __future__ import annotations

from featurelifted import ConfigBox


def test_dot_access() -> None:
    cfg = ConfigBox(host="localhost", port="8080")
    assert cfg.host == "localhost"
    assert cfg.port == "8080"


def test_bool_yes_no() -> None:
    cfg = ConfigBox(enabled="yes", disabled="no")
    assert cfg.bool("enabled") is True
    assert cfg.bool("disabled") is False


def test_int_coercion() -> None:
    cfg = ConfigBox(retries="3")
    assert cfg.int("retries") == 3
