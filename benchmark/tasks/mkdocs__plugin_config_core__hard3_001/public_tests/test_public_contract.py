
from featurelifted import PluginCollection, PluginConfig


def test_plugin_collection_runs_event_by_priority():
    collection = PluginCollection()
    hooks = {
        "a.on_config": lambda **kw: "a",
        "b.on_config": lambda **kw: "b",
    }
    collection.load(
        [PluginConfig("a", priority=10), PluginConfig("b", priority=1)],
        hook_registry=hooks,
    )
    assert collection.run_event("on_config") == ["b", "a"]
