
from featurelifted import Machine


class Model:
    def __init__(self):
        self.state = None
        self.log = []


def test_machine_runs_transition():
    model = Model()
    Machine(
        model,
        states=["a", "b"],
        initial="a",
        transitions=[{"trigger": "go", "source": "a", "dest": "b"}],
    )
    model.go()
    assert model.state == "b"
