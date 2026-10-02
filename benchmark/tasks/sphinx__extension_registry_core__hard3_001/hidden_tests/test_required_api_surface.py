"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ComponentRegistry,
    ExtensionMetadata,
    ExtensionError,
)


def test_required_api_surface():
    assert isinstance(ComponentRegistry, type)
    assert hasattr(ComponentRegistry, 'add_directive')
    assert ComponentRegistry is not None
    assert hasattr(ComponentRegistry, 'load_extension')
    assert isinstance(ExtensionMetadata, type)
    assert issubclass(ExtensionError, BaseException)
