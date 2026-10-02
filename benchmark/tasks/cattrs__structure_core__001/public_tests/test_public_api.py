from __future__ import annotations

import dataclasses

import attrs

from featurelifted import Converter, structure, unstructure


@attrs.define
class Point:
    x: int
    y: int


@dataclasses.dataclass
class Label:
    text: str


def test_attrs_roundtrip() -> None:
    converter = Converter()
    inst = Point(1, 2)
    payload = converter.unstructure(inst)
    assert payload == {"x": 1, "y": 2}
    assert converter.structure(payload, Point) == inst


def test_dataclass_roundtrip() -> None:
    converter = Converter()
    inst = Label("north")
    payload = converter.unstructure(inst)
    assert payload == {"text": "north"}
    assert converter.structure(payload, Label) == inst


def test_module_level_helpers() -> None:
    inst = Point(3, 4)
    payload = unstructure(inst)
    assert payload == {"x": 3, "y": 4}
    assert structure(payload, Point) == inst
