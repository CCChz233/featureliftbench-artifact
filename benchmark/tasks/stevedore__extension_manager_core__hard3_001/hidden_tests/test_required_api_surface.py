"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    EntryPointSpec,
    ExtensionManager,
    NamedExtensionManager,
    NoMatches,
    MultipleMatches,
    error_on_conflict,
    ignore_conflicts,
    Extension,
)


def test_required_api_surface():
    assert isinstance(EntryPointSpec, type)
    assert isinstance(ExtensionManager, type)
    assert hasattr(ExtensionManager, 'map')
    assert hasattr(ExtensionManager, 'names')
    assert ExtensionManager is not None
    assert hasattr(ExtensionManager, '__getitem__')
    assert isinstance(NamedExtensionManager, type)
    assert hasattr(NamedExtensionManager, 'names')
    assert issubclass(NoMatches, BaseException)
    assert issubclass(MultipleMatches, BaseException)
    assert callable(error_on_conflict)
    assert callable(ignore_conflicts)
    assert isinstance(Extension, type)
    assert Extension is not None
    extension = Extension("demo", None, None, None)
    assert hasattr(extension, 'obj')
