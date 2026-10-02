"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    clean,
    Cleaner,
    ALLOWED_TAGS,
    ALLOWED_ATTRIBUTES,
    ALLOWED_PROTOCOLS,
)


def test_required_api_surface():
    assert callable(clean)
    assert isinstance(Cleaner, type)
    assert ALLOWED_TAGS is not None
    assert ALLOWED_ATTRIBUTES is not None
    assert ALLOWED_PROTOCOLS is not None
