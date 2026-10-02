
from featurelifted import EvictionPolicyPlanner


def test_evict_least_recently_used():
    planner = EvictionPolicyPlanner()
    planner.set("a", size=2)
    planner.set("b", size=2)
    planner.touch("a")
    evicted = planner.evict(2)
    assert evicted == ["b"]
