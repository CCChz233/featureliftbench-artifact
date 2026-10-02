from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import Interval, IntervalTree


def test_chop_splits_intervals() -> None:
    tree = IntervalTree([Interval(0, 10)])
    tree.chop(3, 7)
    assert len(tree) == 2
    assert sorted(tree) == [Interval(0, 3), Interval(7, 10)]


def test_chop_datafunc() -> None:
    def datafunc(iv: Interval, islower: bool) -> str:
        oldlimit = iv[islower]
        return f"oldlimit: {oldlimit}, islower: {islower}"

    tree = IntervalTree([Interval(0, 10)])
    tree.chop(3, 7, datafunc)
    assert sorted(tree) == [
        Interval(0, 3, "oldlimit: 10, islower: True"),
        Interval(7, 10, "oldlimit: 0, islower: False"),
    ]


def test_remove_overlap_multiple() -> None:
    tree = IntervalTree(
        [Interval(-1.1, 1.1), Interval(-0.5, 1.5), Interval(0.5, 1.7)]
    )
    tree.remove_overlap(0, 0.5)
    assert set(tree) == {Interval(0.5, 1.7)}


def test_envelop_vs_overlap() -> None:
    tree = IntervalTree([Interval(4, 7), Interval(5, 9), Interval(6, 10)])
    assert tree.envelop(6, 10) == {Interval(6, 10)}
    overlap_hits = tree.overlap(6, 10)
    assert Interval(4, 7) in overlap_hits
    assert Interval(5, 9) in overlap_hits
    assert Interval(6, 10) in overlap_hits


def test_distinct_data_same_range() -> None:
    tree = IntervalTree(
        [Interval(-10, 10), Interval(-10, 10), Interval(-10, 10, "tag")]
    )
    assert len(tree) == 2
    assert Interval(-10, 10) in tree
    assert Interval(-10, 10, "tag") in tree


def test_remove_envelop() -> None:
    tree = IntervalTree(
        [Interval(-1.1, 1.1), Interval(-0.5, 1.5), Interval(0.5, 1.7)]
    )
    tree.remove_envelop(-1.0, 1.5)
    assert set(tree) == {Interval(-1.1, 1.1), Interval(0.5, 1.7)}


def test_complex_point_query() -> None:
    tree = IntervalTree(
        [Interval(4, 7), Interval(5, 9), Interval(6, 10), Interval(8, 15)]
    )
    at_nine = tree.at(9)
    assert at_nine == {Interval(6, 10), Interval(8, 15)}
    assert tree[9] == at_nine


def test_no_intervaltree_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(
        r"^\s*(?:from intervaltree|import intervaltree)\b", re.MULTILINE
    )
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
