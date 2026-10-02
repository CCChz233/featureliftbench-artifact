import pytest
from featurelifted import BadSignature, URLSafeTimedSerializer

def test_roundtrip_and_salt_separation():
    one = URLSafeTimedSerializer("secret", salt="one", now=lambda: 100)
    token = one.dumps({"name": "Ada", "roles": ["admin"]})
    assert one.loads(token, now=100) == {"name": "Ada", "roles": ["admin"]}
    with pytest.raises(BadSignature):
        URLSafeTimedSerializer("secret", salt="two", now=lambda: 100).loads(token, now=100)

def test_tampering_raises_bad_signature():
    serializer = URLSafeTimedSerializer("secret", now=lambda: 10)
    token = serializer.dumps([1, 2, 3])
    with pytest.raises(BadSignature):
        serializer.loads(token[:-1] + ("A" if token[-1] != "A" else "B"), now=10)
