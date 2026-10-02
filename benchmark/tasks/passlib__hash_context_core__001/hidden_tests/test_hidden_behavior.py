from __future__ import annotations

from featurelifted import CryptContext


def test_context_hash_includes_rounds() -> None:
    ctx = CryptContext(schemes=["pbkdf2_sha256"], pbkdf2_sha256__default_rounds=12)
    digest = ctx.hash("secret")
    assert ctx.identify(digest) == "pbkdf2_sha256"
    assert "$pbkdf2-sha256$12$" in digest


def test_context_verify_and_update_roundtrip() -> None:
    ctx = CryptContext(schemes=["pbkdf2_sha256"], pbkdf2_sha256__default_rounds=2)
    old = ctx.hash("pw")
    assert ctx.verify("pw", old)
    new = ctx.hash("pw")
    assert ctx.verify("pw", new)
