
from featurelifted import EvictionPolicyPlanner


def test_tag_filtered_eviction():
    planner = EvictionPolicyPlanner()
    planner.set("a", size=2, tag="hot")
    planner.set("b", size=2, tag="cold")
    evicted = planner.evict(2, tag="cold")
    assert evicted == ["b"]
    assert planner.total_size() == 2


def test_purge_expired_order():
    planner = EvictionPolicyPlanner()
    planner.set("old", expire_at=10.0)
    planner.set("new", expire_at=20.0)
    removed = planner.purge_expired(15.0)
    assert removed == ["old"]


def test_touch_updates_lru():
    planner = EvictionPolicyPlanner()
    planner.set("a", size=2)
    planner.set("b", size=2)
    planner.touch("b")
    evicted = planner.evict(2)
    assert evicted == ["a"]
