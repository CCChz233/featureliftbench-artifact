"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Environment,
    Extension,
    nodes,
    ext,
)


def test_required_api_surface():
    assert isinstance(Environment, type)
    assert hasattr(Environment, 'from_string')
    assert hasattr(Environment, 'iter_extensions')
    assert isinstance(Extension, type)
    assert nodes is not None
    assert isinstance(getattr(nodes, 'CallBlock'), type)
    assert ext is not None
    assert callable(getattr(ext, 'do'))
    assert callable(getattr(ext, 'loopcontrols'))
