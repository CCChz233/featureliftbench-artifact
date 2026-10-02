from featurelifted import Environment
from featurelifted import Extension


class _LoExtension(Extension):
    priority = 10
    tags = set()

    def preprocess(self, source, name, filename=None):
        return source.replace("[[", "{{").replace("]]", "}}")


class _HiExtension(Extension):
    priority = 1
    tags = {"hi"}

    def parse(self, parser):
        from featurelifted import nodes

        lineno = next(parser.stream).lineno
        body = parser.parse_statements(("name:endhi",), drop_needle=True)
        return nodes.CallBlock(self.call_method("_render_hi"), [], [], body).set_lineno(lineno)

    def _render_hi(self, caller):
        return "HI:" + caller()


def test_extension_ordering_by_priority() -> None:
    class _T1(Extension):
        priority = 1

    class _T2(Extension):
        priority = 2

    env = Environment(extensions=[_T2, _T1])
    ordered = [type(ext) for ext in env.iter_extensions()]
    assert ordered == [_T1, _T2]


def test_preprocess_extension_rewrites_delimiters() -> None:
    env = Environment(extensions=[_LoExtension])
    tmpl = env.from_string("[[ name ]]")
    assert tmpl.render(name="Ann") == "Ann"


def test_custom_extension_tag_renders() -> None:
    env = Environment(extensions=[_HiExtension])
    tmpl = env.from_string("{% hi %}world{% endhi %}")
    assert tmpl.render() == "HI:world"
