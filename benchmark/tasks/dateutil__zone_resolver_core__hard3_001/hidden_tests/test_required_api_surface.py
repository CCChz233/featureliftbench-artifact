"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ZoneResolver,
    parse_tzfile,
    UnknownZoneError,
    InvalidTZFileError,
)


def test_required_api_surface():
    assert isinstance(ZoneResolver, type)
    assert hasattr(ZoneResolver, 'load_zone')
    assert hasattr(ZoneResolver, 'get')
    assert hasattr(ZoneResolver, 'register_alias')
    assert callable(parse_tzfile)
    assert issubclass(UnknownZoneError, BaseException)
    assert issubclass(InvalidTZFileError, BaseException)
