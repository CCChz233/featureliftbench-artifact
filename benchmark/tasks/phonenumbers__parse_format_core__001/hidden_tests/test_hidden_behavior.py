from __future__ import annotations

import pytest

from featurelifted import PhoneNumberFormat, format_number, is_valid_number, parse
from featurelifted.phonenumberutil import NumberParseException


def test_gb_national_equals_e164_parse() -> None:
    a = parse("+442083661177", None)
    b = parse("020 8366 1177", "GB")
    assert a.country_code == b.country_code == 44
    assert a.national_number == b.national_number


def test_invalid_region_raises() -> None:
    with pytest.raises(NumberParseException):
        parse("not-a-phone", "US")


def test_is_valid_and_e164_us() -> None:
    num = parse("+12025550123", None)
    assert is_valid_number(num)
    assert format_number(num, PhoneNumberFormat.E164) == "+12025550123"
