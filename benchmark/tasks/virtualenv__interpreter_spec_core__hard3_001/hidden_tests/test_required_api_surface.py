"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse_spec,
    match_version,
    discover_paths,
    InvalidInterpreterSpec,
)


def test_required_api_surface():
    assert callable(parse_spec)
    assert callable(match_version)
    assert callable(discover_paths)
    assert issubclass(InvalidInterpreterSpec, BaseException)
