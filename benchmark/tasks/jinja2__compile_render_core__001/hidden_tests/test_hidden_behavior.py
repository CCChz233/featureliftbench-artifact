from featurelifted import Environment
from featurelifted.compiler import generate
from featurelifted.runtime import Context


def test_macro_render_and_caller() -> None:
    env = Environment()
    tmpl = env.from_string(
        "{% macro greet(name) %}Hi {{ name }}{% endmacro %}{{ greet('Ann') }}"
    )
    assert tmpl.render() == "Hi Ann"


def test_compiler_module_required_for_set_block() -> None:
    env = Environment()
    tree = env.parse("{% set x = 1 %}{{ x + 1 }}")
    source = generate(tree, env, None, None)
    assert "x" in source


def test_runtime_context_exported_vars() -> None:
    env = Environment()
    tmpl = env.from_string("{% set x = 5 %}{{ x }}")
    assert tmpl.render() == "5"
