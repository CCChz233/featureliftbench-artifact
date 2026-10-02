from __future__ import annotations

from featurelifted import parse


def test_parse_function_and_class() -> None:
    module = parse(
        "class C:\n"
        "    def m(self, x: int = 1) -> int:\n"
        "        return x + 1\n"
    )
    cls = module.body[0]
    assert cls.name == "C"
    fn = cls.body[0]
    assert fn.name == "m"
    assert fn.returns.as_string() == "int"
