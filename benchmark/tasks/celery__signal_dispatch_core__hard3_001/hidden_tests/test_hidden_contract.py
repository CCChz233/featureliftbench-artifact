
import gc

from featurelifted import Signal


class Sender:
    pass


def test_sender_filtering():
    sig = Signal("demo")
    sender = Sender()
    hits = []
    sig.connect(lambda: hits.append("all"))
    sig.connect(lambda: hits.append("one"), sender=sender)
    sig.send()
    sig.send(sender=sender)
    assert hits == ["all", "all", "one"]


def test_dispatch_uid_allows_duplicate_callables():
    sig = Signal("demo")
    seen = []
    sig.connect(lambda: seen.append(1), dispatch_uid="a")
    sig.connect(lambda: seen.append(2), dispatch_uid="b")
    sig.send()
    assert seen == [1, 2]


def test_exception_capture_in_send():
    sig = Signal("demo")

    def boom():
        raise RuntimeError("boom")

    sig.connect(boom)
    responses = sig.send()
    assert isinstance(responses[0][1], RuntimeError)


def test_weak_receiver_cleanup():
    sig = Signal("demo")

    class Obj:
        def handler(self):
            return 1

    obj = Obj()
    sig.connect(obj.handler, weak=True)
    del obj
    gc.collect()
    assert sig.send() == []
