import pytest
from featurelifted import BadSignature, SignatureExpired, URLSafeTimedSerializer

def test_expiry_boundary_and_error_type():
    serializer = URLSafeTimedSerializer("secret", now=lambda: 100)
    token = serializer.dumps({"ok": True})
    assert serializer.loads(token, max_age=5, now=105) == {"ok": True}
    with pytest.raises(SignatureExpired):
        serializer.loads(token, max_age=5, now=106)

def test_wrong_key_and_malformed_token():
    token = URLSafeTimedSerializer("a", now=lambda: 1).dumps("x")
    with pytest.raises(BadSignature):
        URLSafeTimedSerializer("b", now=lambda: 1).loads(token, now=1)
    with pytest.raises(BadSignature):
        URLSafeTimedSerializer("a").loads("not-a-token")
