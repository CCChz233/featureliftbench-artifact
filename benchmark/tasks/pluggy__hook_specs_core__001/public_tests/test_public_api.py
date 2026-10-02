from __future__ import annotations

import pytest

from featurelifted import HookimplMarker
from featurelifted import HookspecMarker
from featurelifted import PluginManager
from featurelifted import PluginValidationError


def test_unknown_hook_argument_rejected() -> None:
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

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)

    with pytest.raises(PluginValidationError):
        manager.register(BadPlugin(), name="bad")


def test_check_pending_requires_optional_for_unknown_hooks() -> None:
    hookspec = HookspecMarker("demo")
    hookimpl = HookimplMarker("demo")

    class Spec:
        @hookspec
        def known(self):
            """Declared hook."""

    class Plugin:
        @hookimpl(optionalhook=True)
        def unknown(self):
            return "ok"

    manager = PluginManager("demo")
    manager.add_hookspecs(Spec)
    manager.register(Plugin())

    manager.check_pending()
