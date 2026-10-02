import asyncio, inspect, pytest
from featurelifted import decorate, decorator

def test_invalid_calls_follow_original_signature():
    @decorator(lambda func, *a, **k: func(*a, **k))
    def f(a, *, b): return a + b
    with pytest.raises(TypeError): f(1, 2)

def test_async_caller_and_wrapped():
    async def caller(func, *args, **kwargs): return await func(*args, **kwargs) + 1
    async def base(value): return value * 2
    wrapped = decorate(base, caller)
    assert inspect.iscoroutinefunction(wrapped)
    assert wrapped.__wrapped__ is base
    assert asyncio.run(wrapped(3)) == 7
