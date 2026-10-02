"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Environment,
    filters,
    tests,
    runtime,
)


def test_required_api_surface():
    assert isinstance(Environment, type)
    assert hasattr(Environment, 'call_filter')
    assert hasattr(Environment, 'call_test')
    assert hasattr(Environment, 'from_string')
    assert filters is not None
    assert getattr(filters, 'FILTERS') is not None
    assert tests is not None
    assert getattr(tests, 'TESTS') is not None
    assert runtime is not None
    assert isinstance(getattr(runtime, 'Undefined'), type)
