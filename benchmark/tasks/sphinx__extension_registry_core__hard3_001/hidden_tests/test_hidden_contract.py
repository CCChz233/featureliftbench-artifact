
import pytest

from featurelifted import ComponentRegistry, ExtensionError


def test_duplicate_directive_requires_override():
    registry = ComponentRegistry()
    registry.add_directive("demo", object)
    with pytest.raises(ExtensionError):
        registry.add_directive("demo", object)
    registry.add_directive("demo", list, override=True)
    assert registry.directives["demo"] is list


def test_setup_errors_are_wrapped():
    registry = ComponentRegistry()

    def bad_setup(app):
        raise RuntimeError("boom")

    with pytest.raises(ExtensionError):
        registry.load_extension("bad", bad_setup)
