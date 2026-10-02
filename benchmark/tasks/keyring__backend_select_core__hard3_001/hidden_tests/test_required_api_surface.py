"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ChainerBackend,
    MemoryBackend,
    select_backend,
    Backend,
    BackendNotFound,
    Credential,
    ErrorBackend,
    FailBackend,
    PasswordDeleteError,
    PasswordSetError,
)


def test_required_api_surface():
    assert isinstance(ChainerBackend, type)
    assert hasattr(ChainerBackend, 'get_password')
    assert hasattr(ChainerBackend, 'set_password')
    assert isinstance(MemoryBackend, type)
    assert hasattr(MemoryBackend, 'get_credential')
    assert hasattr(MemoryBackend, 'get_password')
    assert hasattr(MemoryBackend, 'set_password')
    assert callable(select_backend)
    assert isinstance(Backend, type)
    assert issubclass(BackendNotFound, BaseException)
    assert isinstance(Credential, type)
    assert isinstance(ErrorBackend, type)
    assert isinstance(FailBackend, type)
    assert issubclass(PasswordDeleteError, BaseException)
    assert issubclass(PasswordSetError, BaseException)
