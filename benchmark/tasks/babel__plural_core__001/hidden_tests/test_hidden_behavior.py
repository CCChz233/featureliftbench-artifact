from __future__ import annotations

import pytest

from featurelifted import Locale, PluralRule


def test_plural_rule_expression_edges() -> None:
    rule = PluralRule({"one": "n is 1", "few": "n in 2..4"})
    assert rule(1) == "one"
    assert rule(3) == "few"
    assert rule(5) == "other"

    with pytest.raises(ValueError):
        PluralRule({"bogus": "n is 1"})


def test_locale_plural_categories_multilingual() -> None:
    assert Locale.parse("ru").plural_form(21) == "one"
    assert Locale.parse("ru").plural_form(22) == "few"
    assert Locale.parse("fr").plural_form(0) == "one"
    assert Locale.parse("ja").plural_form(5) == "other"
    assert Locale.parse("pl").plural_form(22) == "few"
    assert Locale.parse("pl").plural_form(100) == "many"


def test_plural_rule_string_and_float_operands() -> None:
    rule = PluralRule.parse({"one": "n is 1"})
    assert rule(1) == "one"
    assert rule(1.0) == "one"
