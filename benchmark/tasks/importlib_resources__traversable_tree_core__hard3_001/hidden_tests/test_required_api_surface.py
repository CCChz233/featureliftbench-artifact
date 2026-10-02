"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    TraversalError,
    files,
    read_binary,
    read_text,
    MemoryTraversable,
)


def test_required_api_surface():
    assert issubclass(TraversalError, BaseException)
    assert callable(files)
    assert callable(read_binary)
    assert callable(read_text)
    assert isinstance(MemoryTraversable, type)
    assert hasattr(MemoryTraversable, 'directory')
    assert hasattr(MemoryTraversable, 'joinpath')
