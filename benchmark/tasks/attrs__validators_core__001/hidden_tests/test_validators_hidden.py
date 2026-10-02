from __future__ import annotations

import pytest

from featurelifted import define, field, validate
from featurelifted import validators as v


@define
class Bundle:
    code: str = field(validator=v.matches_re(r"^[A-Z]{3}-\d+$"))
    tags: list[str] = field(validator=v.deep_iterable(v.instance_of(str), v.min_len(1)))


def test_matches_re_and_deep_iterable() -> None:
    bundle = Bundle("ABC-42", ["a", "b"])
    validate(bundle)

    with pytest.raises(ValueError):
        Bundle("bad", ["a"])

    with pytest.raises(TypeError):
        Bundle("ABC-42", ["a", 1])


@define
class MappingBox:
    scores: dict[str, int] = field(
        validator=v.deep_mapping(
            key_validator=v.instance_of(str),
            value_validator=v.instance_of(int),
        )
    )


def test_deep_mapping_validates_keys_and_values() -> None:
    MappingBox({"a": 1})

    with pytest.raises(TypeError):
        MappingBox({1: 2})

    with pytest.raises(TypeError):
        MappingBox({"a": "b"})


@define
class OptionalFlag:
    note: str | None = field(validator=v.optional(v.instance_of(str)))


def test_optional_allows_none_and_validates_present_values() -> None:
    OptionalFlag(None)
    OptionalFlag("ok")

    with pytest.raises(TypeError):
        OptionalFlag(1)


def test_set_disabled_skips_validation() -> None:
    @define
    class Strict:
        value: int = field(validator=v.instance_of(int))

    v.set_disabled(True)
    try:
        obj = Strict("not-int")  # type: ignore[arg-type]
        validate(obj)
    finally:
        v.set_disabled(False)

    with pytest.raises(TypeError):
        Strict("not-int")  # type: ignore[arg-type]
