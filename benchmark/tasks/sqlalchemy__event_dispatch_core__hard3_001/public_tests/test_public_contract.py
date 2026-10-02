
from featurelifted import EventTarget, dispatch, listen


class Target(EventTarget):
    pass


def test_dispatch_invokes_listener():
    seen = []
    listen(Target, "created", lambda: seen.append(1))
    dispatch(Target, "created")
    assert seen == [1]
