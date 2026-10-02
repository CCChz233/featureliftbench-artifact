from __future__ import annotations

import pytest

from featurelifted import Registry
from featurelifted.exceptions import NoSuchAnchor, Unresolvable
from featurelifted.jsonschema import DRAFT202012, UnknownDialect


def test_fragment_ref_into_defs() -> None:
    doc = DRAFT202012.create_resource(
        {
            "type": "object",
            "properties": {"child": {"$ref": "#/$defs/inner"}},
            "$defs": {"inner": {"type": "string"}},
        }
    )
    registry = Registry().with_resource("https://example.com/doc", doc)
    resolved = registry.resolver("https://example.com/doc").lookup("#/$defs/inner")
    assert resolved.contents == {"type": "string"}


def test_anchor_lookup() -> None:
    doc = DRAFT202012.create_resource({"$anchor": "foo", "type": "number"})
    registry = Registry().with_resource("https://example.com/doc", doc)
    resolved = registry.resolver("https://example.com/doc").lookup("#foo")
    assert resolved.contents["type"] == "number"


def test_unknown_dialect_and_missing_anchor() -> None:
    from featurelifted import Resource

    with pytest.raises(UnknownDialect):
        Resource.from_contents({"$schema": "https://example.com/unknown"})

    doc = DRAFT202012.create_resource({"type": "string"})
    registry = Registry().with_resource("https://example.com/doc", doc)
    with pytest.raises(NoSuchAnchor):
        registry.resolver("https://example.com/doc").lookup("#missing")


def test_unresolvable_external_ref() -> None:
    wrapper = DRAFT202012.create_resource({"$ref": "https://example.com/missing"})
    registry = Registry().with_resource("https://example.com/here", wrapper)
    resolved = registry.resolver("https://example.com/here").lookup("#")
    with pytest.raises(Unresolvable):
        resolved.resolver.lookup("https://example.com/missing")
