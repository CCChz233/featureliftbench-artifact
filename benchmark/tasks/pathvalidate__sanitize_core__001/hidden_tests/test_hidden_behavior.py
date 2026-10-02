from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import (
    ErrorReason,
    ReservedNameError,
    ValidationError,
    is_valid_filename,
    sanitize_filename,
    sanitize_filepath,
    validate_filename,
    validate_filepath,
)


def test_windows_reserved_name_sanitize() -> None:
    assert sanitize_filename("CON", platform="windows") == "CON_"
    assert is_valid_filename("CON_", platform="windows")


def test_windows_reserved_name_validate_raises() -> None:
    with pytest.raises(ReservedNameError) as exc:
        validate_filename("CON", platform="windows")
    assert exc.value.reason == ErrorReason.RESERVED_NAME
    assert exc.value.reserved_name == "CON"


def test_sanitize_filepath_reserved_segment() -> None:
    assert sanitize_filepath("abc/CON/xyz", platform="universal") == "abc/CON_/xyz"
    validate_filepath("abc/CON_/xyz", platform="universal")


def test_invalid_character_error_reason() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_filename("a<b", platform="universal")
    assert exc.value.reason == ErrorReason.INVALID_CHARACTER
    assert not is_valid_filename("a<b", platform="universal")


def test_filepath_reserved_name_metadata() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_filepath("PRN", platform="windows")
    assert exc.value.reason == ErrorReason.RESERVED_NAME
    assert exc.value.reserved_name == "PRN"


def test_no_pathvalidate_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from pathvalidate|import pathvalidate)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
