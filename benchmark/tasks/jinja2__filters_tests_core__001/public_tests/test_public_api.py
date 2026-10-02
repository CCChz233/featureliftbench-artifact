from featurelifted import Environment


def test_capitalize_filter_in_template() -> None:
    env = Environment()
    tmpl = env.from_string('{{ "hello"|capitalize }}')
    assert tmpl.render() == "Hello"


def test_call_filter_directly() -> None:
    env = Environment()
    assert env.call_filter("upper", "abc") == "ABC"
