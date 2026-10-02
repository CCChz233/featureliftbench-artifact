import gc
from featurelifted import Signal

def test_weak_receiver_cleanup():
    signal = Signal()
    class Receiver:
        def __call__(self, sender, **kw): return "ok"
    receiver = Receiver()
    signal.connect(receiver)
    assert len(signal.send(None)) == 1
    del receiver; gc.collect()
    assert signal.send(None) == []

def test_connected_to_scope_and_disconnect():
    signal, calls = Signal(), []
    def receiver(sender, **kw): calls.append(sender)
    with signal.connected_to(receiver, sender="x"):
        signal.send("x"); signal.send("y")
    signal.send("x")
    assert calls == ["x"]
