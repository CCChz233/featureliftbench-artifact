"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    FixtureDef,
    FixtureLookupError,
    FixtureRegistry,
    deduplicate_names,
    fixture,
    getfixturemarker,
    resolve_fixture_closure,
)


def test_required_api_surface():
    assert isinstance(FixtureDef, type)
    assert issubclass(FixtureLookupError, BaseException)
    assert isinstance(FixtureRegistry, type)
    assert hasattr(FixtureRegistry, 'register')
    assert callable(deduplicate_names)
    assert callable(fixture)
    assert callable(getfixturemarker)
    assert callable(resolve_fixture_closure)
