"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    MarkerRegistry,
    Marker,
    UnknownMarkerWarning,
)


def test_required_api_surface():
    assert isinstance(MarkerRegistry, type)
    assert hasattr(MarkerRegistry, 'from_ini')
    assert hasattr(MarkerRegistry, 'check_unknown')
    assert hasattr(MarkerRegistry, 'get')
    assert hasattr(MarkerRegistry, 'merge_plugin_markers')
    assert hasattr(MarkerRegistry, 'register')
    assert isinstance(Marker, type)
    assert issubclass(UnknownMarkerWarning, BaseException)
