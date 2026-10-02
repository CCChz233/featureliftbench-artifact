from featurelifted import Environment


def test_render_simple_interpolation() -> None:
    env = Environment()
    tmpl = env.from_string("Hello {{ name }}!")
    assert tmpl.render(name="World") == "Hello World!"


def test_render_if_for_blocks() -> None:
    env = Environment()
    tmpl = env.from_string(
        "{% for n in items %}{% if n %}{{ n }}{% endif %}{% endfor %}"
    )
    assert tmpl.render(items=[1, 0, 2]) == "12"
