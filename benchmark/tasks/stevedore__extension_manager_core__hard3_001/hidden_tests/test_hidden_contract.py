import pytest

from featurelifted import (
    EntryPointSpec,
    ExtensionManager,
    MultipleMatches,
    NamedExtensionManager,
    error_on_conflict,
)


class PluginA:
    def run(self):
        return "A"


class PluginB:
    def run(self):
        return "B"


def test_load_failure_callback_gets_manager_entrypoint_and_exception():
    seen = []

    def bad_loader():
        raise ImportError("missing optional dependency")

    def callback(manager, entry_point, exc):
        seen.append((manager.namespace, entry_point.name, type(exc).__name__, str(exc)))

    eps = [
        EntryPointSpec("bad", "plugins:Bad", "demo", loader=bad_loader),
        EntryPointSpec("good", "plugins:Good", "demo", loader=lambda: PluginA),
    ]

    manager = ExtensionManager("demo", entry_points=eps, on_load_failure_callback=callback)

    assert manager.names() == ["good"]
    assert seen == [("demo", "bad", "ImportError", "missing optional dependency")]


def test_duplicate_names_default_to_last_extension():
    eps = [
        EntryPointSpec("dup", "plugins:A", "demo", loader=lambda: PluginA),
        EntryPointSpec("dup", "plugins:B", "demo", loader=lambda: PluginB),
    ]

    manager = ExtensionManager("demo", entry_points=eps)

    assert manager.names() == ["dup", "dup"]
    assert manager["dup"].plugin is PluginB


def test_duplicate_names_can_raise_multiple_matches():
    eps = [
        EntryPointSpec("dup", "plugins:A", "demo", loader=lambda: PluginA),
        EntryPointSpec("dup", "plugins:B", "demo", loader=lambda: PluginB),
    ]

    manager = ExtensionManager("demo", entry_points=eps, conflict_resolver=error_on_conflict)

    with pytest.raises(MultipleMatches):
        manager["dup"]


def test_map_exception_policy_can_ignore_or_propagate():
    eps = [
        EntryPointSpec("a", "plugins:A", "demo", loader=lambda: PluginA),
        EntryPointSpec("b", "plugins:B", "demo", loader=lambda: PluginB),
    ]

    def mapper(ext):
        if ext.name == "a":
            raise RuntimeError("skip")
        return ext.name

    tolerant = ExtensionManager("demo", entry_points=eps, propagate_map_exceptions=False)
    strict = ExtensionManager("demo", entry_points=eps, propagate_map_exceptions=True)

    assert tolerant.map(mapper) == ["b"]
    with pytest.raises(RuntimeError, match="skip"):
        strict.map(mapper)


def test_named_extension_manager_filters_reports_missing_and_orders_names():
    missing = []
    eps = [
        EntryPointSpec("a", "plugins:A", "demo", loader=lambda: PluginA),
        EntryPointSpec("b", "plugins:B", "demo", loader=lambda: PluginB),
        EntryPointSpec("c", "plugins:C", "demo", loader=lambda: PluginA),
    ]

    manager = NamedExtensionManager(
        "demo",
        ["b", "missing", "a"],
        entry_points=eps,
        name_order=True,
        on_missing_entrypoints_callback=lambda names: missing.extend(sorted(names)),
    )

    assert manager.names() == ["b", "a"]
    assert missing == ["missing"]
