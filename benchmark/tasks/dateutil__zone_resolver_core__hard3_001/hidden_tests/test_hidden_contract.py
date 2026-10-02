
import pytest

from featurelifted import InvalidTZFileError, UnknownZoneError, ZoneResolver

TZIF = b"TZif" + bytes([0]) + bytes(39)


def test_alias_resolution():
    resolver = ZoneResolver()
    resolver.register_alias("US/Eastern", "America/New_York")
    zone = resolver.load_zone("US/Eastern", {"America/New_York": TZIF})
    assert zone.name == "America/New_York"
    assert resolver.get("US/Eastern") is zone


def test_circular_alias_raises():
    resolver = ZoneResolver()
    resolver.register_alias("a", "b")
    resolver.register_alias("b", "a")
    with pytest.raises(UnknownZoneError):
        resolver.load_zone("a", {})


def test_invalid_tzfile_header():
    with pytest.raises(InvalidTZFileError):
        __import__("featurelifted").parse_tzfile(b"bad")
