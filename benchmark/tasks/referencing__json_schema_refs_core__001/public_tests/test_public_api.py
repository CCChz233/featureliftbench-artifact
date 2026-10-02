from __future__ import annotations

from featurelifted import Registry
from featurelifted.jsonschema import DRAFT202012


def test_external_ref_resolution() -> None:
    target = DRAFT202012.create_resource({"type": "integer"})
    wrapper = DRAFT202012.create_resource({"$ref": "https://example.com/target"})
    registry = Registry().with_resources(
        [
            ("https://example.com/target", target),
            ("https://example.com/wrapper", wrapper),
        ]
    )
    resolver = registry.resolver("https://example.com/wrapper")
    resolved = resolver.lookup("#").resolver.lookup("https://example.com/target")
    assert resolved.contents == {"type": "integer"}
