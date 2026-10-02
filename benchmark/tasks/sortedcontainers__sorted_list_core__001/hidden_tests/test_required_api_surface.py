"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    SortedList,
)


def test_required_api_surface():
    assert isinstance(SortedList, type)
    assert hasattr(SortedList, '_check')
    assert SortedList is not None
    assert SortedList is not None
    assert hasattr(SortedList, '_reset')
    assert hasattr(SortedList, 'add')
    assert hasattr(SortedList, 'bisect')
    assert hasattr(SortedList, 'bisect_left')
    assert hasattr(SortedList, 'bisect_right')
    assert hasattr(SortedList, 'index')
    assert hasattr(SortedList, 'irange')
    assert hasattr(SortedList, 'islice')
    assert hasattr(SortedList, 'update')
    assert hasattr(SortedList, '__delitem__')
