from __future__ import annotations

from featurelifted import parse


def test_async_and_match_statements() -> None:
    async_mod = parse("async def f():\n    await g()\n")
    assert async_mod.body[0].name == "f"
    await_node = async_mod.body[0].body[0].value
    assert await_node.value.func.name == "g"

    match_mod = parse("match x:\n  case 1:\n    pass\n")
    match_stmt = match_mod.body[0]
    assert match_stmt.__class__.__name__ == "Match"
    assert match_stmt.cases[0].pattern.value.value == 1


def test_defaults_and_docstring() -> None:
    module = parse(
        "class C:\n"
        '    """docstring"""\n'
        "\n"
        "    def m(self, x: int = 1) -> int:\n"
        "        return x + 1\n"
    )
    cls = module.body[0]
    assert cls.doc_node.value == "docstring"
    fn = cls.body[0]
    assert fn.args.annotations[1].as_string() == "int"
    assert fn.args.defaults[0].value == 1


def test_module_as_string_contains_def() -> None:
    module = parse("def f():\n    return 1\n")
    text = module.as_string()
    assert "def f" in text
    assert "return 1" in text
