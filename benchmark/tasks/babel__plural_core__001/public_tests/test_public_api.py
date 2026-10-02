from __future__ import annotations

from featurelifted import Locale, PluralRule


def test_plural_rule_and_english_locale() -> None:
    rule = PluralRule({"one": "n is 1"})
    assert rule(1) == "one"
    assert rule(5) == "other"

    en = Locale.parse("en")
    assert en.plural_form(1) == "one"
    assert en.plural_form(0) == "other"
