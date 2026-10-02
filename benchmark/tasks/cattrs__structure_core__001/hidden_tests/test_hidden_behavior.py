from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Optional

import attrs
import pytest

from featurelifted import Converter
from featurelifted.errors import ClassValidationError, ForbiddenExtraKeysError
from featurelifted.gen import make_dict_structure_fn, make_dict_unstructure_fn, override


@attrs.define
class Inner:
    value: int


@attrs.define
class Outer:
    inner: Inner
    label: str = "default"


@dataclasses.dataclass
class Foo:
    bar: str


@attrs.define
class Container:
    foos: list[Foo]


def test_nested_attrs_and_dataclass() -> None:
    converter = Converter()
    inst = Container([Foo("alpha"), Foo("beta")])
    payload = {"foos": [{"bar": "alpha"}, {"bar": "beta"}]}
    assert converter.unstructure(inst) == payload
    assert converter.structure(payload, Container) == inst


def test_structure_hook_rename_override() -> None:
    converter = Converter()
    hook = make_dict_structure_fn(Outer, converter, label=override(rename="name"))
    converter.register_structure_hook(Outer, hook)
    obj = converter.structure({"inner": {"value": 7}, "name": "edge"}, Outer)
    assert obj.label == "edge"
    assert obj.inner.value == 7


def test_unstructure_omit_if_default() -> None:
    converter = Converter()
    hook = make_dict_unstructure_fn(Outer, converter, label=override(omit_if_default=True))
    converter.register_unstructure_hook(Outer, hook)
    inst = Outer(Inner(2))
    payload = converter.unstructure(inst)
    assert "label" not in payload
    assert payload == {"inner": {"value": 2}}


def test_forbid_extra_keys() -> None:
    converter = Converter(forbid_extra_keys=True)

    @attrs.define
    class Simple:
        a: int

    with pytest.raises(ClassValidationError) as excinfo:
        converter.structure({"a": 1, "unexpected": 2}, Simple)
    assert len(excinfo.value.exceptions) == 1
    assert isinstance(excinfo.value.exceptions[0], ForbiddenExtraKeysError)


def test_optional_none_field() -> None:
    @attrs.define
    class Maybe:
        note: Optional[str] = None

    converter = Converter()
    inst = Maybe(None)
    payload = converter.unstructure(inst)
    assert payload == {"note": None}
    assert converter.structure({"note": None}, Maybe) == inst


def test_no_cattrs_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from cattrs|import cattrs)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
