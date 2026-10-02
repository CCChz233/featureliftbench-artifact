"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    PluralRule,
    Locale,
)


def test_required_api_surface():
    assert isinstance(PluralRule, type)
    assert hasattr(PluralRule, 'parse')
    assert isinstance(Locale, type)
    assert hasattr(Locale, 'parse')
    assert Locale is not None
