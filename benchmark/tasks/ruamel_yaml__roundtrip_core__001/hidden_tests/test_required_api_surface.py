"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    YAML,
    round_trip_load,
    round_trip_dump,
    CommentedMap,
)


def test_required_api_surface():
    assert YAML is not None
    assert callable(round_trip_load)
    assert callable(round_trip_dump)
    assert isinstance(CommentedMap, type)
    assert CommentedMap is not None
