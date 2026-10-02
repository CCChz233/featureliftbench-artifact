"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired,
)


def test_required_api_surface():
    assert isinstance(URLSafeTimedSerializer, type)
    assert hasattr(URLSafeTimedSerializer, 'dumps')
    assert hasattr(URLSafeTimedSerializer, 'loads')
    assert issubclass(BadSignature, BaseException)
    assert issubclass(SignatureExpired, BaseException)
