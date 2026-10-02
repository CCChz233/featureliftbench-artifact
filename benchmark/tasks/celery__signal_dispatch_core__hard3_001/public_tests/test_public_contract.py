
from featurelifted import Signal


def test_signal_send_invokes_receiver():
    sig = Signal("demo")
    seen = []
    sig.connect(lambda: seen.append(1))
    sig.send()
    assert seen == [1]
