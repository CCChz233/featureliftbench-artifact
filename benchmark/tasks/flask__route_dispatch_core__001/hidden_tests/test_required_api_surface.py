"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    App,
    Response,
)


def test_required_api_surface():
    assert isinstance(App, type)
    assert hasattr(App, 'dispatch')
    assert hasattr(App, 'errorhandler')
    assert hasattr(App, 'route')
    assert isinstance(Response, type)
