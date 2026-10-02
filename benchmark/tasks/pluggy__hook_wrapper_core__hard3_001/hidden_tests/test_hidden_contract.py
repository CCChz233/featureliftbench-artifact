
from featurelifted import HookCaller


def test_tryfirst_trylast_ordering():
    hook = HookCaller("demo")
    order = []
    hook.add_hookimpl(lambda: order.append("normal"))
    hook.add_hookimpl(lambda: order.append("first"), tryfirst=True)
    hook.add_hookimpl(lambda: order.append("last"), trylast=True)
    hook()
    assert order == ["first", "normal", "last"]


def test_call_extra_restores_state():
    hook = HookCaller("demo")
    hook.add_hookimpl(lambda: 1)
    result = hook.call_extra([lambda: 2], {})
    assert result == [2, 1]
    assert len(hook.get_hookimpls()) == 1


def test_direct_call_on_historic_raises():
    hook = HookCaller("demo", historic=True)
    try:
        hook()
        raised = False
    except RuntimeError:
        raised = True
    assert raised
