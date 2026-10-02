"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    naturaltime,
    naturaldelta,
    naturaldate,
    naturalday,
    precisedelta,
)


def test_required_api_surface():
    assert callable(naturaltime)
    assert callable(naturaldelta)
    assert callable(naturaldate)
    assert callable(naturalday)
    assert callable(precisedelta)
