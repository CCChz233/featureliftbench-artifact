
from featurelifted import PluginCollection, PluginConfig, validate_plugin_config


def test_disabled_plugins_are_excluded():
    collection = PluginCollection()
    hooks = {"enabled.on_config": lambda **kw: 1, "disabled.on_config": lambda **kw: 2}
    collection.load(
        [PluginConfig("enabled"), PluginConfig("disabled", enabled=False)],
        hook_registry=hooks,
    )
    assert collection.names == ["enabled"]
    assert collection.run_event("on_config") == [1]


def test_validate_plugin_config_reports_schema_errors():
    errors = validate_plugin_config("search", {"lang": 1}, {"lang": str, "enabled": bool})
    joined = " ".join(errors).lower()
    assert errors
    assert "enabled" in joined
    assert "lang" in joined


def test_unexpected_option_reported():
    errors = validate_plugin_config("x", {"extra": 1}, {})
    assert any("unexpected option extra" in e for e in errors)
