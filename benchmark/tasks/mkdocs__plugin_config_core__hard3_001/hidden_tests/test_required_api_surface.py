"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    PluginConfig,
    PluginCollection,
    validate_plugin_config,
)


def test_required_api_surface():
    assert isinstance(PluginConfig, type)
    assert isinstance(PluginCollection, type)
    assert hasattr(PluginCollection, 'load')
    assert PluginCollection is not None
    assert hasattr(PluginCollection, 'run_event')
    assert callable(validate_plugin_config)
