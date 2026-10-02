from featurelifted import FixtureDef
from featurelifted import FixtureRegistry
from featurelifted import fixture
from featurelifted import getfixturemarker
from featurelifted import resolve_fixture_closure


def test_resolve_closure_adds_fixture_dependencies() -> None:
    registry = FixtureRegistry()
    registry.register(
        FixtureDef(argname="db", argnames=("conn",), baseid="", scope="session")
    )
    registry.register(
        FixtureDef(argname="conn", argnames=(), baseid="", scope="module")
    )

    closure, arg2defs = resolve_fixture_closure(
        {"", "pkg"},
        ("db",),
        registry,
    )

    assert closure == ["db", "conn"]
    assert set(arg2defs) == {"db", "conn"}


def test_getfixturemarker_on_decorated_function() -> None:
    @fixture(scope="module", name="resource")
    def _resource() -> str:
        return "ok"

    marker = getfixturemarker(_resource)
    assert marker is not None
    assert marker.scope == "module"
    assert marker.name == "resource"
