from __future__ import annotations

import pytest

from featurelifted import HookimplMarker
from featurelifted import HookspecMarker
from featurelifted import PluginManager
from featurelifted import PluginValidationError


def test_firstresult_and_hookwrapper_result_mutation() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec(firstresult=True)
        def choose(self, value):
            """Return the first non-None result."""

        @hookspec
        def wrapped(self, value):
            """Return wrapped values."""

    class Base:
        @hookimpl
        def choose(self, value):
            return None

        @hookimpl
        def wrapped(self, value):
            return value + "-base"

    class Last:
        @hookimpl(trylast=True)
        def choose(self, value):
            return value + "-last"

    class Wrapper:
        @hookimpl(hookwrapper=True)
        def wrapped(self, value):
            outcome = yield
            results = outcome.get_result()
            results.append("wrapper")

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)
    manager.register(Base())
    manager.register(Last())
    manager.register(Wrapper())

    assert manager.hook.choose(value="x") == "x-last"
    assert manager.hook.wrapped(value="x") == ["x-base", "wrapper"]


def test_validation_unregister_and_plugin_names() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec
        def step(self, value):
            """Known arguments only."""

    class BadPlugin:
        @hookimpl
        def step(self, value, unknown):
            return value

    class GoodPlugin:
        @hookimpl
        def step(self, value):
            return value.upper()

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)

    with pytest.raises(PluginValidationError):
        manager.register(BadPlugin(), name="bad")

    plugin = GoodPlugin()
    manager.register(plugin, name="good")
    assert manager.get_name(plugin) == "good"
    assert manager.hook.step(value="ok") == ["OK"]
    assert manager.unregister(name="good") is plugin
    assert not manager.has_plugin("good")


def test_hook_historic_and_subset_hooknames() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec
        def alpha(self, value):
            """First hook."""

        @hookspec
        def beta(self, value):
            """Second hook."""

    class Plugin:
        @hookimpl
        def alpha(self, value):
            return value + "-a"

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)
    manager.register(Plugin())
    assert manager.hook.alpha(value="x") == ["x-a"]
    assert set(manager.hook.__dict__.keys()) >= {"alpha", "beta"}
