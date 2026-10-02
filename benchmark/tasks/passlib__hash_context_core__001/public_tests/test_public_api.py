from __future__ import annotations

from featurelifted import CryptContext


def test_hash_and_verify_pbkdf2() -> None:
    ctx = CryptContext(schemes=["pbkdf2_sha256"], pbkdf2_sha256__default_rounds=1)
    digest = ctx.hash("hunter2")
    assert digest.startswith("$pbkdf2-sha256$")
    assert ctx.verify("hunter2", digest)
    assert not ctx.verify("wrong", digest)
