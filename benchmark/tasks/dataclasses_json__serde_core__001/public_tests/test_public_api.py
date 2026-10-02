from __future__ import annotations

from dataclasses import dataclass, field

from featurelifted import LetterCase, dataclass_json, config


@dataclass_json
@dataclass
class Person:
    name: str
    age: int


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class CamelPerson:
    given_name: str


def test_basic_json_roundtrip() -> None:
    inst = Person("Ada", 36)
    assert inst.to_json() == '{"name": "Ada", "age": 36}'
    assert Person.from_json('{"name": "Ada", "age": 36}') == inst


def test_dict_roundtrip() -> None:
    inst = Person("Grace", 85)
    payload = inst.to_dict()
    assert payload == {"name": "Grace", "age": 85}
    assert Person.from_dict(payload) == inst


def test_class_level_camel_case() -> None:
    inst = CamelPerson("Alice")
    assert inst.to_json() == '{"givenName": "Alice"}'
    assert CamelPerson.from_json('{"givenName": "Alice"}') == inst


def test_field_name_override() -> None:
    @dataclass_json
    @dataclass
    class AliasPerson:
        given_name: str = field(metadata=config(field_name="givenName"))

    inst = AliasPerson("Bob")
    assert inst.to_dict() == {"givenName": "Bob"}
    assert AliasPerson.from_dict({"givenName": "Bob"}) == inst
