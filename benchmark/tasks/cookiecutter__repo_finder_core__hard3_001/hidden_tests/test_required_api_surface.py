"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    RepoFinder,
    expand_abbreviation,
    safe_join,
    UnsafePathError,
)


def test_required_api_surface():
    assert isinstance(RepoFinder, type)
    assert hasattr(RepoFinder, 'find_template')
    assert callable(expand_abbreviation)
    assert callable(safe_join)
    assert issubclass(UnsafePathError, BaseException)
