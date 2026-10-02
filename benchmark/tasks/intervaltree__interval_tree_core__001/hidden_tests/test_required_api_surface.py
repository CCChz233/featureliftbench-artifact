"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Interval,
    IntervalTree,
)


def test_required_api_surface():
    assert isinstance(Interval, type)
    assert isinstance(IntervalTree, type)
    assert hasattr(IntervalTree, 'at')
    assert hasattr(IntervalTree, 'chop')
    assert hasattr(IntervalTree, 'envelop')
    assert hasattr(IntervalTree, 'overlap')
    assert hasattr(IntervalTree, 'remove_envelop')
    assert hasattr(IntervalTree, 'remove_overlap')
    assert hasattr(IntervalTree, '__contains__')
    assert hasattr(IntervalTree, '__getitem__')
