
import pytest

from featurelifted import YamaleError, make_schema, validate


def test_strict_mode_rejects_extra_keys():
    schema = make_schema("name: str\n")
    with pytest.raises(YamaleError):
        validate(schema, [({"name": "Ada", "extra": 1}, "doc")], strict=True)


def test_include_and_list_validator():
    schema = make_schema("name: str\ntags: list(str)\ncontact: include('contact')\n---\ncontact:\n  email: str\n")
    data = {"name": "Ada", "tags": ["a"], "contact": {"email": "a@example.com"}}
    results = validate(schema, [(data, "doc")], strict=False, _raise_error=False)
    assert results[0].isValid()


def test_bool_non_strict_coercion():
    schema = make_schema("flag: bool\n")
    results = validate(schema, [({"flag": "true"}, "doc")], strict=False, _raise_error=False)
    assert results[0].isValid()
