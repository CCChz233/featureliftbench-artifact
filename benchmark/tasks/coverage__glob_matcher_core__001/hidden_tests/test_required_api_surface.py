"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    GlobMatcher,
    prep_patterns,
    globs_to_regex,
    exceptions,
)


def test_required_api_surface():
    assert isinstance(GlobMatcher, type)
    assert hasattr(GlobMatcher, 'match')
    assert callable(prep_patterns)
    assert callable(globs_to_regex)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'ConfigError'), BaseException)
