from __future__ import annotations

from featurelifted import Interval, IntervalTree


def test_add_and_point_query() -> None:
    tree = IntervalTree()
    tree.add(Interval(0, 10, "base"))
    tree.addi(10, 20)
    assert len(tree) == 2
    assert tree[5] == {Interval(0, 10, "base")}
    assert tree.overlaps(15)


def test_remove_interval() -> None:
    tree = IntervalTree([Interval(-10, 10), Interval(10, 20)])
    tree.remove(Interval(-10, 10))
    assert Interval(-10, 10) not in tree
    assert tree.overlaps(15)


def test_overlap_range() -> None:
    tree = IntervalTree([Interval(4, 7), Interval(5, 9)])
    hits = tree.overlap(4, 6)
    assert Interval(4, 7) in hits
    assert tree.overlaps(4, 6)
