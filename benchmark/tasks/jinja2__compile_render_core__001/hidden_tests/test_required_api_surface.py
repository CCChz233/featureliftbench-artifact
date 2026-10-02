"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Environment,
    compiler,
    runtime,
)


def test_required_api_surface():
    assert isinstance(Environment, type)
    assert hasattr(Environment, 'from_string')
    assert hasattr(Environment, 'parse')
    assert compiler is not None
    assert callable(getattr(compiler, 'generate'))
    assert runtime is not None
    assert isinstance(getattr(runtime, 'Context'), type)
