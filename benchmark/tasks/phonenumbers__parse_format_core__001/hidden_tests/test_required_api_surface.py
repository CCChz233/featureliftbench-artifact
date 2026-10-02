"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    PhoneNumberFormat,
    NumberParseException,
    format_number,
    is_valid_number,
    parse,
    phonenumberutil,
)


def test_required_api_surface():
    assert isinstance(PhoneNumberFormat, type)
    assert PhoneNumberFormat is not None
    assert PhoneNumberFormat is not None
    assert PhoneNumberFormat is not None
    assert issubclass(NumberParseException, BaseException)
    assert callable(format_number)
    assert callable(is_valid_number)
    assert callable(parse)
    assert phonenumberutil is not None
    assert issubclass(getattr(phonenumberutil, 'NumberParseException'), BaseException)
