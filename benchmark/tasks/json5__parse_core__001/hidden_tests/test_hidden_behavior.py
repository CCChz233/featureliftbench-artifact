import pytest

from featurelifted import loads


def test_hex_and_plus_numeric_literals() -> None:
    value = loads("{mask: 0xFF, delta: +12}")

    assert value == {"mask": 255, "delta": 12}


def test_duplicate_keys_rejected_when_disabled() -> None:
    with pytest.raises(ValueError, match="Duplicate key"):
        loads("{a: 1, a: 2}", allow_duplicate_keys=False)


def test_malformed_input_reports_position() -> None:
    with pytest.raises(ValueError, match=r"column \d+"):
        loads("{broken: }")
