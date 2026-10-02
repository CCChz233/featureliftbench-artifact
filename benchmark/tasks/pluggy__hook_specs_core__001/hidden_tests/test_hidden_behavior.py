from __future__ import annotations

import pytest

from featurelifted import HookimplMarker
from featurelifted import HookspecMarker
from featurelifted import PluginManager
from featurelifted import PluginValidationError


def test_historic_hook_replays_for_late_registration() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec(historic=True)
        def configure(self, value):
            """Remember configure calls."""

    class Plugin:
        @hookimpl
        def configure(self, value):
            return value + "-configured"

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)
    results: list[str] = []
    manager.hook.configure.call_historic(
        result_callback=results.append,
        kwargs={"value": "seed"},
    )
    assert results == []
    manager.register(Plugin())
    assert results == ["seed-configured"]


def test_hookwrapper_must_be_generator() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec
        def step(self, value):
            """Single hook."""

    class BadWrapper:
        @hookimpl(hookwrapper=True)
        def step(self, value):
            return value

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)

    with pytest.raises(PluginValidationError, match="generator function"):
        manager.register(BadWrapper())


def test_historic_hookwrapper_combination_rejected() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec(historic=True)
        def step(self, value):
            """Historic hook."""

    class Wrapper:
        @hookimpl(hookwrapper=True)
        def step(self, value):
            outcome = yield
            return outcome.get_result()

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)

    with pytest.raises(PluginValidationError, match="historic incompatible"):
        manager.register(Wrapper())
