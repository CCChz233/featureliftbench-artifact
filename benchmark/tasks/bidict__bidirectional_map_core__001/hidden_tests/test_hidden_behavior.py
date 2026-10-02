from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import (
    KeyAndValueDuplicationError,
    ON_DUP_RAISE,
    OrderedBidict,
    ValueDuplicationError,
    bidict,
    frozenbidict,
    inverted,
)


def test_on_dup_raise_value_collision() -> None:
    mapping = bidict({"a": 1, "b": 2}, on_dup=ON_DUP_RAISE)
    with pytest.raises(ValueDuplicationError):
        mapping["c"] = 1


def test_key_and_value_duplication_error() -> None:
    mapping = bidict({"a": 1, "b": 2}, on_dup=ON_DUP_RAISE)
    with pytest.raises(KeyAndValueDuplicationError):
        mapping["b"] = 1


def test_ordered_move_to_end() -> None:
    ordered = OrderedBidict({"a": 1, "b": 2, "c": 3})
    ordered.move_to_end("a", last=False)
    assert list(ordered.keys()) == ["a", "b", "c"]
    ordered.move_to_end("b", last=True)
    assert list(ordered.keys()) == ["a", "c", "b"]


def test_frozenbidict_hash_stable() -> None:
    left = frozenbidict({"k": "v"})
    right = frozenbidict({"k": "v"})
    assert hash(left) == hash(right)


def test_inverted_iterator() -> None:
    mapping = bidict({"a": 1, "b": 2})
    assert list(inverted(mapping)) == [(1, "a"), (2, "b")]


def test_no_bidict_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from bidict|import bidict)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
