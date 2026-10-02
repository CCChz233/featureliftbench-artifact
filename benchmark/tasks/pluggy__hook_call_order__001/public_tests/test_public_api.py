from __future__ import annotations

from featurelifted import HookimplMarker
from featurelifted import HookspecMarker
from featurelifted import PluginManager


def test_basic_hook_registration_and_ordering() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec
        def step(self, value):
            """Transform a value."""

    class First:
        @hookimpl(tryfirst=True)
        def step(self, value):
            return f"first:{value}"

    class Last:
        @hookimpl(trylast=True)
        def step(self, value):
            return f"last:{value}"

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)
    manager.register(Last(), name="last")
    manager.register(First(), name="first")

    assert manager.hook.step(value="x") == ["first:x", "last:x"]
    assert manager.get_plugin("first") is not None
    assert manager.has_plugin("last")
