"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ExtensionConfigStore,
    merge_extension_configs,
    filter_enabled_extensions,
    recursive_update,
)


def test_required_api_surface():
    assert isinstance(ExtensionConfigStore, type)
    assert hasattr(ExtensionConfigStore, 'disable')
    assert hasattr(ExtensionConfigStore, 'enabled')
    assert hasattr(ExtensionConfigStore, 'get_extensions')
    assert callable(merge_extension_configs)
    assert callable(filter_enabled_extensions)
    assert callable(recursive_update)
