
from featurelifted import EventTarget, dispatch, listen, remove


class Target(EventTarget):
    pass


class Child(Target):
    pass


def test_once_and_remove_during_dispatch_and_propagation():
    calls = []

    def once_fn():
        calls.append("once")

    def during():
        calls.append("during")
        remove(Target, "evt", during)

    listen(Target, "evt", during)
    listen(Target, "evt", once_fn, once=True)
    dispatch(Target, "evt")
    dispatch(Target, "evt")
    assert calls == ["during", "once"]

    child_calls = []
    listen(Target, "child", lambda: child_calls.append(1), propagate=True)
    dispatch(Child, "child")
    assert child_calls == [1]


def test_named_kwargs_dispatch():
    seen = {}
    listen(Target, "evt", lambda value=None: seen.update({"value": value}), named=True)
    dispatch(Target, "evt", value=7)
    assert seen == {"value": 7}
