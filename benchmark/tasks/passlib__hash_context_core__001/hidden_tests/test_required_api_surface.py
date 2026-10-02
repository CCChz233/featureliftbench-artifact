"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    CryptContext,
)


def test_required_api_surface():
    assert isinstance(CryptContext, type)
    assert hasattr(CryptContext, 'hash')
    assert hasattr(CryptContext, 'identify')
    assert hasattr(CryptContext, 'verify')
