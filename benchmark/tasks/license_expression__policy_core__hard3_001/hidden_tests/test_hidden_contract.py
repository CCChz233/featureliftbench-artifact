import pytest

from featurelifted import ExpressionParseError, LicenseSymbol, Licensing


def make_licensing():
    return Licensing(
        [
            LicenseSymbol("MIT", aliases=("mit",)),
            LicenseSymbol("BSD-3-Clause", aliases=("bsd",)),
            LicenseSymbol("Apache-2.0", aliases=("apache2",)),
            LicenseSymbol("GPL-2.0-only", aliases=("GPL-2.0", "gpl2")),
            LicenseSymbol("Classpath-exception-2.0", aliases=("Classpath",), is_exception=True),
        ]
    )


def test_parentheses_override_precedence():
    licensing = make_licensing()

    parsed = licensing.parse("(mit or bsd) and apache2", validate=True)

    assert parsed.render() == "(MIT OR BSD-3-Clause) AND Apache-2.0"


def test_plain_symbol_cannot_be_used_as_with_exception():
    licensing = make_licensing()

    with pytest.raises(ExpressionParseError, match="plain license symbol"):
        licensing.parse("MIT WITH Apache-2.0", validate=True, strict=True)


def test_exception_symbol_cannot_be_used_as_plain_license():
    licensing = make_licensing()

    with pytest.raises(ExpressionParseError, match="exception symbol"):
        licensing.parse("Classpath OR MIT", validate=True, strict=True)


def test_validate_reports_unknown_symbol_without_normalized_expression():
    licensing = make_licensing()

    info = licensing.validate("MIT AND UnknownLicense")

    assert info.normalized_expression is None
    assert info.invalid_symbols == ["UnknownLicense"]
    assert info.errors == ["Unknown license symbol: UnknownLicense"]


def test_policy_denies_denied_symbol_even_inside_with_expression():
    licensing = make_licensing()

    result = licensing.evaluate_policy(
        "GPL-2.0 WITH Classpath OR MIT",
        allowed={"MIT", "Classpath-exception-2.0"},
        denied={"GPL-2.0-only"},
    )

    assert result["status"] == "denied"
    assert result["denied"] == ["GPL-2.0-only"]
    assert result["normalized"] == "GPL-2.0-only WITH Classpath-exception-2.0 OR MIT"


def test_unbalanced_parentheses_raise_parse_error():
    licensing = make_licensing()

    with pytest.raises(ExpressionParseError, match="unbalanced"):
        licensing.parse("(MIT OR BSD-3-Clause", validate=True)
