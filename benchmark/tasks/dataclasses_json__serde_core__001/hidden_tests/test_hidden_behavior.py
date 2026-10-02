from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from featurelifted import (
    DataClassJsonMixin,
    Exclude,
    LetterCase,
    Undefined,
    config,
    dataclass_json,
    global_config,
)
from featurelifted.undefined import UndefinedParameterError


@dataclass_json
@dataclass
class CamelFieldPerson:
    given_name: str = field(
        metadata={"dataclasses_json": {"letter_case": LetterCase.CAMEL}}
    )


@dataclass
class EncodeExclude(DataClassJsonMixin):
    public_field: str
    private_field: str = field(metadata=config(exclude=Exclude.ALWAYS))


@dataclass
class EncodeCustom(DataClassJsonMixin):
    public_field: str
    sensitive_field: str = field(
        metadata=config(exclude=lambda value: value.startswith("secret"))
    )


@dataclass_json
@dataclass
class Inner:
    value: int


@dataclass_json
@dataclass
class Outer:
    inner: Inner
    label: str = "default"


@dataclass_json(undefined=Undefined.RAISE)
@dataclass
class StrictPayload:
    endpoint: str


@dataclass_json
@dataclass
class DuplicateCamelKeys:
    given_name_1: str = field(
        metadata={"dataclasses_json": {"letter_case": LetterCase.CAMEL}}
    )
    given_name1: str = field(
        metadata={"dataclasses_json": {"letter_case": LetterCase.CAMEL}}
    )


@dataclass
class Timestamped(DataClassJsonMixin):
    created_at: datetime = field(
        metadata={
            "dataclasses_json": {
                "encoder": lambda dt: dt.isoformat(),
                "decoder": datetime.fromisoformat,
            }
        }
    )


def test_field_level_camel_case() -> None:
    inst = CamelFieldPerson("Alice")
    assert inst.to_json() == '{"givenName": "Alice"}'
    assert CamelFieldPerson.from_json('{"givenName": "Alice"}') == inst


def test_exclude_always() -> None:
    inst = EncodeExclude(public_field="public", private_field="private")
    encoded = inst.to_dict()
    assert encoded == {"public_field": "public"}


def test_exclude_custom_predicate() -> None:
    visible = EncodeCustom(public_field="public", sensitive_field="notsecret")
    hidden = EncodeCustom(public_field="public", sensitive_field="secret")
    assert "sensitive_field" in visible.to_dict()
    assert "sensitive_field" not in hidden.to_dict()


def test_nested_dataclass_roundtrip() -> None:
    inst = Outer(Inner(7), "edge")
    payload = {"inner": {"value": 7}, "label": "edge"}
    assert inst.to_dict() == payload
    assert Outer.from_dict(payload) == inst
    assert inst.to_json() == '{"inner": {"value": 7}, "label": "edge"}'


def test_undefined_raise_on_extra_keys() -> None:
    with pytest.raises(UndefinedParameterError):
        StrictPayload.from_dict(
            {"endpoint": "api", "unexpected_field": [1, 2, 3]}
        )


def test_duplicate_letter_case_encoding_error() -> None:
    with pytest.raises(ValueError, match="Multiple fields map to the same JSON key"):
        DuplicateCamelKeys("Alice", "Bob").to_dict()


def test_global_config_encoder_decoder() -> None:
    global_config.encoders[datetime] = lambda dt: dt.isoformat()
    global_config.decoders[datetime] = datetime.fromisoformat
    try:
        stamp = datetime(2020, 1, 2, 3, 4, 5)
        inst = Timestamped(stamp)
        payload = inst.to_dict()
        assert payload == {"created_at": "2020-01-02T03:04:05"}
        assert Timestamped.from_dict(payload).created_at == stamp
    finally:
        global_config.encoders.pop(datetime, None)
        global_config.decoders.pop(datetime, None)


def test_no_dataclasses_json_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(
        r"^\s*(?:from dataclasses_json|import dataclasses_json)\b",
        re.MULTILINE,
    )
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
