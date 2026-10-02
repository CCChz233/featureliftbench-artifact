from featurelifted import Namespace, Signal

def test_sender_filtering_and_responses():
    signal, seen = Signal(), []
    def any_receiver(sender, **kw): seen.append(("any", sender)); return kw["value"]
    def only_receiver(sender, **kw): seen.append(("only", sender)); return "only"
    signal.connect(any_receiver, weak=False)
    signal.connect(only_receiver, sender="chosen", weak=False)
    assert signal.send("chosen", value=3) == [(any_receiver, 3), (only_receiver, "only")]
    assert signal.send("other", value=4) == [(any_receiver, 4)]

def test_namespace_identity():
    namespace = Namespace()
    assert namespace.signal("ready") is namespace.signal("ready")
    assert namespace.signal("ready") is not namespace.signal("done")
