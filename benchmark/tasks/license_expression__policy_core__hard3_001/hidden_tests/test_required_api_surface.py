"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    LicenseSymbol,
    Licensing,
    ExpressionInfo,
    ExpressionParseError,
)


def test_required_api_surface():
    assert isinstance(LicenseSymbol, type)
    assert LicenseSymbol is not None
    assert isinstance(Licensing, type)
    assert hasattr(Licensing, 'parse')
    assert hasattr(Licensing, 'validate')
    assert hasattr(Licensing, 'license_symbols')
    assert hasattr(Licensing, 'evaluate_policy')
    assert isinstance(ExpressionInfo, type)
    assert issubclass(ExpressionParseError, BaseException)
    license_symbol = LicenseSymbol("MIT")
    assert hasattr(license_symbol, 'key')
