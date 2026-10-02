"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    compile_path,
    Route,
    Mount,
    Router,
    Match,
)


def test_required_api_surface():
    assert callable(compile_path)
    assert isinstance(Route, type)
    assert hasattr(Route, 'matches')
    assert isinstance(Mount, type)
    assert isinstance(Router, type)
    assert hasattr(Router, 'match')
    assert hasattr(Router, 'url_path_for')
    assert isinstance(Match, type)
    assert Match is not None
