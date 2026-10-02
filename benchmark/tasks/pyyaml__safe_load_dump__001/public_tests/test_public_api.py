from __future__ import annotations

from featurelifted import safe_dump
from featurelifted import safe_load


def test_safe_load_basic_mapping_sequence_and_scalars() -> None:
    data = safe_load("a: 1\nb:\n - x\n - y\nflag: true\nempty: null\n")

    assert data == {"a": 1, "b": ["x", "y"], "flag": True, "empty": None}


def test_safe_dump_sort_keys_output() -> None:
    assert safe_dump({"b": [1, 2], "a": True}, sort_keys=True) == (
        "a: true\nb:\n- 1\n- 2\n"
    )
