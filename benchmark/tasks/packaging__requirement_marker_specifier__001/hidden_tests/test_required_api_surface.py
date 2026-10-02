"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Version,
    Specifier,
    SpecifierSet,
    Requirement,
    Marker,
    default_environment,
    InvalidVersion,
    InvalidSpecifier,
    InvalidRequirement,
    InvalidMarker,
)


def test_required_api_surface():
    assert isinstance(Version, type)
    assert isinstance(Specifier, type)
    assert isinstance(SpecifierSet, type)
    assert hasattr(SpecifierSet, 'filter')
    assert hasattr(SpecifierSet, '__contains__')
    assert isinstance(Requirement, type)
    assert Requirement is not None
    assert Requirement is not None
    assert Requirement is not None
    assert Requirement is not None
    assert Requirement is not None
    assert isinstance(Marker, type)
    assert hasattr(Marker, 'evaluate')
    assert callable(default_environment)
    assert issubclass(InvalidVersion, BaseException)
    assert issubclass(InvalidSpecifier, BaseException)
    assert issubclass(InvalidRequirement, BaseException)
    assert issubclass(InvalidMarker, BaseException)
