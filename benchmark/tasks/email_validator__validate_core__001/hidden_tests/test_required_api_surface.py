"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    validate_email,
    ValidatedEmail,
    EmailNotValidError,
    EmailSyntaxError,
    EmailUndeliverableError,
)


def test_required_api_surface():
    assert validate_email is not None
    assert isinstance(ValidatedEmail, type)
    assert issubclass(EmailNotValidError, BaseException)
    assert issubclass(EmailSyntaxError, BaseException)
    assert issubclass(EmailUndeliverableError, BaseException)
