import pytest

from featurelifted import EntryPointSpec, ExtensionManager, NoMatches


class Plugin:
    def __init__(self, prefix=""):
        self.prefix = prefix

    def label(self, value):
        return f"{self.prefix}{value}"


def test_extension_manager_loads_matching_namespace():
    eps = [
        EntryPointSpec("alpha", "plugins:Alpha", "demo", loader=lambda: Plugin),
        EntryPointSpec("ignored", "plugins:Ignored", "other", loader=lambda: Plugin),
    ]

    manager = ExtensionManager("demo", entry_points=eps)

    assert manager.names() == ["alpha"]
    assert "alpha" in manager
    assert manager["alpha"].plugin is Plugin
    assert manager["alpha"].entry_point_target == "plugins:Alpha"


def test_invoke_on_load_and_map_method():
    eps = [EntryPointSpec("alpha", "plugins:Alpha", "demo", loader=lambda: Plugin)]
    manager = ExtensionManager("demo", entry_points=eps, invoke_on_load=True, invoke_args=("pre-",))

    assert manager.map_method("label", "value") == ["pre-value"]


def test_map_raises_no_matches_when_empty():
    manager = ExtensionManager("demo", entry_points=[])

    with pytest.raises(NoMatches):
        manager.map(lambda ext: ext.name)
