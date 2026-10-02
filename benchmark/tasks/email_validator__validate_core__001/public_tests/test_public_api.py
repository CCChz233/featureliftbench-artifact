from __future__ import annotations

import pytest

from featurelifted import EmailNotValidError, EmailSyntaxError, ValidatedEmail, validate_email


def test_validate_basic_ascii_email() -> None:
    result = validate_email("user@example.com", check_deliverability=False)
    assert isinstance(result, ValidatedEmail)
    assert result.normalized == "user@example.com"
    assert result.local_part == "user"
    assert result.domain == "example.com"
    assert result.ascii_email == "user@example.com"


def test_validate_plus_addressing() -> None:
    result = validate_email("user+tag@example.org", check_deliverability=False)
    assert result.normalized == "user+tag@example.org"
    assert result.local_part == "user+tag"


def test_invalid_missing_at_sign() -> None:
    with pytest.raises(EmailSyntaxError) as exc_info:
        validate_email("not-an-email", check_deliverability=False)
    assert "@" in str(exc_info.value)
    assert isinstance(exc_info.value, EmailNotValidError)


def test_invalid_empty_local_part() -> None:
    with pytest.raises(EmailSyntaxError):
        validate_email("@example.com", check_deliverability=False)
