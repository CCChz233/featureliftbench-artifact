from __future__ import annotations

import random
import re
from pathlib import Path

from featurelifted import SortedList


def test_hidden_bisect_with_small_load() -> None:
    slt = SortedList(range(100))
    slt._reset(17)
    slt.update(range(100))
    slt._check()
    assert slt.bisect_left(50) == 100
    assert slt.bisect_right(10) == 22
    assert slt.bisect(200) == 200


def test_hidden_irange_inclusive_bounds() -> None:
    slt = SortedList(range(53))
    slt._reset(7)
    assert list(slt.irange(10, 20, (True, False))) == list(range(10, 20))
    assert list(slt.irange(10, 20, (False, True))) == list(range(11, 21))
    assert list(slt.irange(10, 20, (False, False))) == list(range(11, 20))


def test_hidden_islice_reverse() -> None:
    slt = SortedList(range(53))
    slt._reset(7)
    values = list(range(53))
    for start in range(0, 53, 11):
        for stop in range(start + 1, 53, 13):
            assert list(slt.islice(start, stop, reverse=True)) == values[start:stop][::-1]


def test_hidden_delete_random_invariants() -> None:
    random.seed(0)
    slt = SortedList(range(100))
    slt._reset(17)
    while len(slt) > 0:
        pos = random.randrange(len(slt))
        del slt[pos]
        slt._check()


def test_hidden_index_duplicate_window() -> None:
    slt = SortedList([0] * 10)
    slt._reset(4)
    for start in range(10):
        for stop in range(start, 10):
            assert slt.index(0, start, stop + 1) == start
    assert slt.index(0, -1000) == 0


def test_hidden_check_invariants() -> None:
    slt = SortedList(range(100))
    slt._reset(4)
    for val in range(100, 250):
        slt.add(val)
    slt._check()
    assert len(slt._lists) > 1
    assert slt._maxes == [sub[-1] for sub in slt._lists]


def test_no_sortedcontainers_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(
        r"^\s*(?:from sortedcontainers|import sortedcontainers)\b",
        re.MULTILINE,
    )
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
