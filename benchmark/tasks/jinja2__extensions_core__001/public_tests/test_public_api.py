from featurelifted import Environment


def test_loopcontrols_extension_breaks_loop() -> None:
    env = Environment(extensions=["featurelifted.ext.loopcontrols"])
    tmpl = env.from_string(
        "{% for n in range(10) %}{% if n == 3 %}{% break %}{% endif %}{{ n }}{% endfor %}"
    )
    assert tmpl.render() == "012"


def test_do_extension_executes_side_effect() -> None:
    env = Environment(extensions=["featurelifted.ext.do"])
    tmpl = env.from_string("{% set items = [] %}{% do items.append(1) %}{{ items|length }}")
    assert tmpl.render() == "1"
