from featurelifted import LicenseSymbol, Licensing


def make_licensing():
    return Licensing(
        [
            LicenseSymbol("MIT", aliases=("mit",)),
            LicenseSymbol("Apache-2.0", aliases=("Apache License 2.0", "apache2")),
            LicenseSymbol("GPL-2.0-only", aliases=("GPL-2.0", "gpl2")),
            LicenseSymbol("Classpath-exception-2.0", aliases=("Classpath",), is_exception=True),
        ]
    )


def test_alias_normalization_and_precedence_rendering():
    licensing = make_licensing()

    parsed = licensing.parse("gpl2 or apache2 and mit", validate=True)

    assert parsed.render() == "GPL-2.0-only OR (Apache-2.0 AND MIT)"
    assert [symbol.key for symbol in licensing.license_symbols(parsed)] == ["GPL-2.0-only", "Apache-2.0", "MIT"]


def test_with_exception_normalizes_aliases():
    licensing = make_licensing()

    parsed = licensing.parse("GPL-2.0 WITH Classpath", validate=True)

    assert parsed.render() == "GPL-2.0-only WITH Classpath-exception-2.0"


def test_policy_allows_known_allowed_symbols():
    licensing = make_licensing()

    result = licensing.evaluate_policy(
        "apache2 and mit",
        allowed={"Apache-2.0", "MIT"},
        denied={"GPL-2.0-only"},
    )

    assert result["status"] == "allowed"
    assert result["normalized"] == "Apache-2.0 AND MIT"
