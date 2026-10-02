
import pytest

from featurelifted import ActionRegistry, ConfigurationConflictError


def test_duplicate_discriminator_raises():
    registry = ActionRegistry()
    registry.register("route", callable=lambda: 1)
    registry.register("route", callable=lambda: 2)
    with pytest.raises(ConfigurationConflictError):
        registry.commit()


def test_none_discriminator_never_conflicts():
    registry = ActionRegistry()
    registry.register(None, callable=lambda: 1)
    registry.register(None, callable=lambda: 2)
    assert registry.commit() == [1, 2]


def test_introspect_category_filter():
    registry = ActionRegistry()
    registry.register("x", callable=lambda: 1, category="view")
    registry.register("y", callable=lambda: 2, category="route")
    registry.commit()
    assert len(registry.introspect(category="view")) == 1
