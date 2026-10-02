from __future__ import annotations

from featurelifted import bidict, frozenbidict


def test_bidict_forward_and_inverse_lookup() -> None:
    mapping = bidict({"H": "hydrogen", "O": "oxygen"})
    assert mapping["H"] == "hydrogen"
    assert mapping.inverse["hydrogen"] == "H"


def test_bidict_inverse_reflects_updates() -> None:
    mapping = bidict({"a": 1})
    mapping["b"] = 2
    assert mapping.inverse[2] == "b"
    assert set(mapping.inverse.keys()) == {1, 2}


def test_frozenbidict_is_immutable() -> None:
    mapping = frozenbidict({"x": 10})
    assert mapping["x"] == 10
    assert mapping.inverse[10] == "x"
