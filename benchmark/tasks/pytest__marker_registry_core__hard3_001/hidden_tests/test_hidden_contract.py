
import warnings

from featurelifted import MarkerRegistry, UnknownMarkerWarning


def test_merge_plugin_markers_does_not_overwrite():
    registry = MarkerRegistry()
    registry.register("slow", "original")
    registry.merge_plugin_markers({"slow": "plugin", "xfail": "expected failure"})
    assert registry.get("slow").description == "original"
    assert registry.get("xfail").description == "expected failure"


def test_check_unknown_warns():
    registry = MarkerRegistry()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        registry.check_unknown("missing")
    assert any(isinstance(item.message, UnknownMarkerWarning) for item in caught)


def test_check_unknown_strict_raises():
    registry = MarkerRegistry()
    try:
        registry.check_unknown("missing", strict=True)
    except KeyError:
        pass
    else:
        raise AssertionError("strict unknown marker should raise KeyError")
