"""Constitution API-surface coverage generated from public_spec."""

import featurelifted.routing.exceptions

from featurelifted import (
    routing,
)


def test_required_api_surface():
    assert routing is not None
    assert isinstance(getattr(routing, 'Map'), type)
    assert hasattr(getattr(routing, 'Map'), 'bind')
    assert isinstance(getattr(routing, 'Rule'), type)
    assert isinstance(getattr(routing, 'Subdomain'), type)
    assert isinstance(getattr(routing, 'Submount'), type)
    assert getattr(routing, 'exceptions') is not None
    assert issubclass(getattr(getattr(routing, 'exceptions'), 'RequestRedirect'), BaseException)
