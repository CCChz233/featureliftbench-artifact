"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    OptionManager,
    PluginSpec,
    classify_plugins,
    apply_select_ignore,
    OptionSpec,
)


def test_required_api_surface():
    assert isinstance(OptionManager, type)
    assert isinstance(PluginSpec, type)
    assert callable(classify_plugins)
    assert callable(apply_select_ignore)
    assert isinstance(OptionSpec, type)
