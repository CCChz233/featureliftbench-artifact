"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    EvictionPolicyPlanner,
)


def test_required_api_surface():
    assert isinstance(EvictionPolicyPlanner, type)
    assert hasattr(EvictionPolicyPlanner, 'evict')
    assert hasattr(EvictionPolicyPlanner, 'purge_expired')
    assert hasattr(EvictionPolicyPlanner, 'set')
    assert hasattr(EvictionPolicyPlanner, 'total_size')
    assert hasattr(EvictionPolicyPlanner, 'touch')
