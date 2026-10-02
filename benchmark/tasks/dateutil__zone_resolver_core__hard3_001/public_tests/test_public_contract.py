
from featurelifted import ZoneResolver

TZIF = b"TZif" + bytes([0]) + bytes(39)


def test_load_zone_caches():
    resolver = ZoneResolver()
    zone = resolver.load_zone("UTC", {"UTC": TZIF})
    assert zone.name == "UTC"
    assert resolver.get("UTC") is zone
