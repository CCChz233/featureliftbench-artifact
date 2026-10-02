import inspect
from featurelifted import decorator

def test_metadata_signature_and_call_order():
    calls = []
    def caller(func, *args, **kwargs):
        calls.append((args, kwargs)); return func(*args, **kwargs) * 2
    @decorator(caller)
    def add(a: int, b: int = 1) -> int:
        '''add values'''
        return a + b
    assert add(2, b=3) == 10
    assert str(inspect.signature(add)) == "(a: int, b: int = 1) -> int"
    assert add.__name__ == "add" and add.__doc__ == "add values"
    assert calls == [((2,), {"b": 3})]
