
from featurelifted import ActionRegistry


def test_action_registry_executes_in_order():
    registry = ActionRegistry()
    log = []
    registry.register("a", callable=lambda: log.append("a"), order=10)
    registry.register("b", callable=lambda: log.append("b"), order=1)
    registry.commit()
    assert log == ["b", "a"]
