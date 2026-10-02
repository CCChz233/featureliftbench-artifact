import pytest

from featurelifted import FixtureDef
from featurelifted import FixtureLookupError
from featurelifted import FixtureRegistry
from featurelifted import deduplicate_names
from featurelifted import resolve_fixture_closure


def test_deduplicate_names_keeps_first_occurrence_order() -> None:
    names = deduplicate_names(["a", "b", "a"], ["b", "c"])
    assert names == ("a", "b", "c")


def test_closure_sorted_by_scope_descending() -> None:
    registry = FixtureRegistry()
    registry.register(
        FixtureDef(argname="low", argnames=("high",), baseid="", scope="function")
    )
    registry.register(
        FixtureDef(argname="high", argnames=(), baseid="", scope="session")
    )

    closure, _ = resolve_fixture_closure({"": ""}, ("low",), registry)

    assert closure.index("high") < closure.index("low")


def test_fixture_lookup_error_lists_available() -> None:
    registry = FixtureRegistry()
    registry.register(FixtureDef(argname="alpha", argnames=(), baseid="", scope="function"))
    _, arg2defs = resolve_fixture_closure({"": ""}, ("alpha",), registry)
    assert "alpha" in arg2defs

    with pytest.raises(FixtureLookupError) as excinfo:
        raise FixtureLookupError("missing", available=["alpha", "beta"])

    assert "missing" in str(excinfo.value)
    assert "alpha" in str(excinfo.value)
