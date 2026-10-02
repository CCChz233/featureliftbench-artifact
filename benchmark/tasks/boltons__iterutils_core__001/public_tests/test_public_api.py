from __future__ import annotations

from featurelifted import bucketize, chunked, pairwise, unique, windowed


def test_chunked_basic() -> None:
    assert chunked(range(7), 3) == [[0, 1, 2], [3, 4, 5], [6]]


def test_windowed_and_pairwise() -> None:
    assert windowed([1, 2, 3, 4], 3) == [(1, 2, 3), (2, 3, 4)]
    assert pairwise([1, 2, 3]) == [(1, 2), (2, 3)]


def test_unique_and_bucketize() -> None:
    assert unique([1, 2, 1, 3, 2]) == [1, 2, 3]
    assert bucketize(["aa", "b", "ccc"], key=len) == {2: ["aa"], 1: ["b"], 3: ["ccc"]}
