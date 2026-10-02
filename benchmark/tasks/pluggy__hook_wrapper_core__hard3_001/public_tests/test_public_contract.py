
from featurelifted import HookCaller


def test_historic_replays_for_late_registration():
    hook = HookCaller("demo", historic=True)
    seen = []
    hook.call_historic({"value": 1}, result_callback=seen.append)
    hook.add_hookimpl(lambda value: value + 1)
    assert seen == [2]


def test_hookwrapper_runs_teardown():
    hook = HookCaller("demo")
    order = []

    @hook.add_hookwrapper
    def outer():
        order.append("enter")
        yield
        order.append("exit")

    hook.add_hookimpl(lambda: order.append("inner"))
    hook()
    assert order == ["enter", "inner", "exit"]
