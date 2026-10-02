from __future__ import annotations

from featurelifted import SortedList


def test_add_and_iteration() -> None:
    slt = SortedList()
    slt.update([3, 1, 2])
    assert list(slt) == [1, 2, 3]


def test_bisect_and_count() -> None:
    slt = SortedList([1, 2, 2, 3])
    assert slt.bisect_left(2) == 1
    assert slt.bisect_right(2) == 3
    assert slt.count(2) == 2


def test_discard_and_remove() -> None:
    slt = SortedList([1, 2, 3])
    slt.discard(99)
    assert list(slt) == [1, 2, 3]
    slt.remove(2)
    assert list(slt) == [1, 3]
