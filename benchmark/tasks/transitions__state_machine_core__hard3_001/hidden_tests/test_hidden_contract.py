
import pytest

from featurelifted import Machine, MachineError


class Model:
    def __init__(self):
        self.state = None
        self.log = []

    def is_ready(self):
        return True

    def before_go(self):
        self.log.append("before")

    def after_go(self):
        self.log.append("after")


def test_conditional_transition_and_callbacks():
    model = Model()
    Machine(
        model,
        states=["a", "b"],
        initial="a",
        transitions=[{"trigger": "go", "source": "a", "dest": "b", "conditions": "is_ready", "before": "before_go", "after": "after_go"}],
    )
    model.go()
    assert model.state == "b"
    assert model.log == ["before", "after"]


def test_nested_state_name():
    model = Model()
    Machine(model, states=["parent.child"], initial="parent.child")
    assert model.parent.state == "child"


def test_invalid_trigger_raises():
    model = Model()
    Machine(
        model,
        states=["a", "b"],
        initial="a",
        transitions=[{"trigger": "go", "source": "b", "dest": "a"}],
    )
    with pytest.raises(MachineError):
        model.go()
