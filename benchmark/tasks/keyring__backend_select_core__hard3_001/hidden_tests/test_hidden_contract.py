import pytest

from featurelifted import (
    Backend,
    BackendNotFound,
    ChainerBackend,
    ErrorBackend,
    FailBackend,
    MemoryBackend,
    PasswordSetError,
    select_backend,
)


class Negative(Backend):
    priority = -1
    name = "negative"

    def get_password(self, service, username):
        return "nope"


class Working(Backend):
    priority = 1
    name = "working"

    def get_password(self, service, username):
        return f"{service}:{username}"


def test_negative_priority_is_excluded_and_fail_backend_is_default():
    assert isinstance(select_backend([Negative]), FailBackend)

    with pytest.raises(BackendNotFound):
        select_backend([Negative], env={"PYTHON_KEYRING_BACKEND": "negative"})


def test_chainer_skips_backend_errors_on_get_password():
    broken = ErrorBackend("broken", priority=10, error=RuntimeError("unavailable"))
    working = MemoryBackend("working", priority=1)
    working.set_password("svc", "u", "secret")

    backend = ChainerBackend([broken, working])

    assert backend.get_password("svc", "u") == "secret"


def test_chainer_set_password_falls_back_after_failure():
    broken = ErrorBackend("broken", priority=10, error=RuntimeError("readonly"))
    working = MemoryBackend("working", priority=1)
    backend = ChainerBackend([broken, working])

    backend.set_password("svc", "u", "secret")

    assert working.get_password("svc", "u") == "secret"


def test_chainer_set_password_raises_when_all_backends_fail():
    backend = ChainerBackend([ErrorBackend("broken", priority=1, error=RuntimeError("readonly"))])

    with pytest.raises(PasswordSetError):
        backend.set_password("svc", "u", "secret")


def test_get_credential_can_discover_username():
    backend = MemoryBackend("memory", priority=1)
    backend.set_password("svc", "stored-user", "secret")

    credential = backend.get_credential("svc", None)

    assert credential.username == "stored-user"
    assert credential.password == "secret"
