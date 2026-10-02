from featurelifted import Expression
from featurelifted import expression as expr_mod


def test_kwargs_matcher() -> None:
    def matcher(name, **kwargs):
        return name == "req" and kwargs.get("version") == 2

    assert Expression.compile('req(version=2)').evaluate(matcher)


def test_expression_module_scanner() -> None:
    from featurelifted.expression import Scanner, TokenType

    scanner = Scanner("a and b")
    assert scanner.current.type is TokenType.IDENT
