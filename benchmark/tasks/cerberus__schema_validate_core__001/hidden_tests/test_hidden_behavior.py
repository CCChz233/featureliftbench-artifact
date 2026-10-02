from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import Validator


PROFILE_SCHEMA = {
    "city": {"type": "string", "required": True},
    "zip": {"type": "string"},
}

USER_SCHEMA = {
    "name": {"type": "string", "required": True},
    "profile": {
        "type": "dict",
        "required": True,
        "schema": PROFILE_SCHEMA,
    },
}


def test_nested_schema_validation() -> None:
    validator = Validator(USER_SCHEMA)
    assert validator.validate({"name": "Ada", "profile": {"city": "Paris"}})
    assert not validator.validate({"name": "Ada", "profile": {}})
    assert validator.errors["profile"][0]["city"] == ["required field"]


def test_coerce_updates_document() -> None:
    validator = Validator(
        {
            "count": {"type": "integer", "coerce": int, "required": True},
            "ratio": {"type": "float", "coerce": float},
        }
    )
    assert validator.validate({"count": "12", "ratio": "0.5"})
    assert validator.document == {"count": 12, "ratio": 0.5}
    assert not validator.validate({"count": "nope", "ratio": "0.5"})
    assert "count" in validator.errors


def test_nested_list_error_paths() -> None:
    validator = Validator(
        {
            "items": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {"id": {"type": "integer", "required": True}},
                },
            }
        }
    )
    assert not validator.validate({"items": [{"id": "nope"}]})
    nested = validator.errors["items"][0][0][0]["id"]
    assert nested == ["must be of integer type"]


def test_deep_nested_schema_and_coerce_combo() -> None:
    validator = Validator(
        {
            "batch": {
                "type": "dict",
                "schema": {
                    "entries": {
                        "type": "list",
                        "schema": {
                            "type": "dict",
                            "schema": {
                                "qty": {"type": "integer", "coerce": int, "min": 1},
                            },
                        },
                    }
                },
            }
        }
    )
    payload = {"batch": {"entries": [{"qty": "2"}, {"qty": "0"}]}}
    assert not validator.validate(payload)
    assert validator.document["batch"]["entries"][0]["qty"] == 2
    entry_errors = validator.errors["batch"][0]["entries"][0][1][0]["qty"]
    assert entry_errors == ["min value is 1"]


def test_no_cerberus_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from cerberus|import cerberus)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
