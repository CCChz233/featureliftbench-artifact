"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    glom,
    T,
    Coalesce,
    PathAccessError,
)


def test_required_api_surface():
    assert callable(glom)
    assert T is not None
    assert isinstance(Coalesce, type)
    assert issubclass(PathAccessError, BaseException)
