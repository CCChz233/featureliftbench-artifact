from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import EmailNotValidError, EmailSyntaxError, ValidatedEmail, validate_email


def test_idna_domain_normalization() -> None:
    result = validate_email("jeff@臺網中心.tw", check_deliverability=False)
    assert result.domain == "臺網中心.tw"
    assert result.ascii_domain == "xn--fiqq24b10vi0d.tw"
    assert result.normalized == "jeff@臺網中心.tw"
    assert result.ascii_email == "jeff@xn--fiqq24b10vi0d.tw"


def test_quoted_local_part_dequoted() -> None:
    result = validate_email(
        '"de-quoted.local.part"@example.org',
        allow_quoted_local=True,
        check_deliverability=False,
    )
    assert result.local_part == "de-quoted.local.part"
    assert result.normalized == "de-quoted.local.part@example.org"


def test_display_name_parsing() -> None:
    result = validate_email(
        "My Name <me@example.org>",
        allow_display_name=True,
        check_deliverability=False,
    )
    assert result.display_name == "My Name"
    assert result.normalized == "me@example.org"
    assert result.original == "me@example.org"


def test_postmaster_case_insensitive() -> None:
    result = validate_email("POSTMASTER@test", test_environment=True, check_deliverability=False)
    assert result.normalized == "postmaster@test"


def test_reserved_domain_rejected() -> None:
    with pytest.raises(EmailSyntaxError) as exc_info:
        validate_email("me@valid.invalid", check_deliverability=False)
    assert "special-use or reserved name" in str(exc_info.value)


def test_test_environment_allows_dot_test() -> None:
    result = validate_email("anything@mycompany.test", test_environment=True, check_deliverability=False)
    assert result.domain == "mycompany.test"


def test_unicode_nfc_local_part() -> None:
    # Combining sequence s\u0323\u0307 NFC-normalizes to \u1E69
    result = validate_email(
        "s\u0323\u0307@nfc.tld",
        check_deliverability=False,
        test_environment=True,
    )
    assert result.local_part == "\u1E69"
    assert result.normalized == "\u1E69@nfc.tld"


def test_smtputf8_local_part() -> None:
    result = validate_email("ñoñó@example.tld", check_deliverability=False, test_environment=True)
    assert result.smtputf8 is True
    assert result.ascii_email is None
    assert result.normalized == "ñoñó@example.tld"


def test_domain_literal_ipv4() -> None:
    result = validate_email("me@[127.0.0.1]", allow_domain_literal=True, check_deliverability=False)
    assert result.domain == "[127.0.0.1]"
    assert repr(result.domain_address) == "IPv4Address('127.0.0.1')"


def test_no_email_validator_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from email_validator|import email_validator)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
