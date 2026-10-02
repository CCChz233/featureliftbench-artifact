from __future__ import annotations

from featurelifted import PhoneNumberFormat, format_number, parse


def test_parse_e164_and_format() -> None:
    num = parse("+442083661177", None)
    assert format_number(num, PhoneNumberFormat.E164) == "+442083661177"
    assert "+44" in format_number(num, PhoneNumberFormat.INTERNATIONAL)


def test_parse_national_us() -> None:
    num = parse("(202) 555-0123", "US")
    assert format_number(num, PhoneNumberFormat.NATIONAL).startswith("(202)")
