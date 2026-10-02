from __future__ import annotations

import pytest

from featurelifted import YAMLError
from featurelifted import safe_dump
from featurelifted import safe_dump_all
from featurelifted import safe_load
from featurelifted import safe_load_all
from featurelifted.constructor import ConstructorError


def test_anchors_aliases_merge_keys_and_dates() -> None:
    content = (
        "defaults: &defaults\n"
        "  retries: 3\n"
        "  enabled: true\n"
        "prod:\n"
        "  <<: *defaults\n"
        "  host: example.com\n"
    )

    assert safe_load(content) == {
        "defaults": {"retries": 3, "enabled": True},
        "prod": {"retries": 3, "enabled": True, "host": "example.com"},
    }


def test_multi_document_dump_load_and_unsafe_tags_rejected() -> None:
    docs = list(safe_load_all("---\na: 1\n---\nb: 2\n"))
    assert docs == [{"a": 1}, {"b": 2}]

    dumped = safe_dump_all(docs, sort_keys=True)
    assert list(safe_load_all(dumped)) == docs

    with pytest.raises(ConstructorError):
        safe_load('!!python/object/apply:os.system ["echo bad"]')


def test_parse_errors_and_flow_style_dumping() -> None:
    with pytest.raises(YAMLError):
        safe_load("a: [1, 2\n")

    assert safe_dump({"items": [{"x": 1}, {"y": 2}]}, default_flow_style=True) == (
        "{items: [{x: 1}, {y: 2}]}\n"
    )


def test_unicode_scalar_and_timestamp_tag() -> None:
    doc = safe_load("when: 2020-01-02\nemoji: \U0001f600\n")
    assert doc["when"].year == 2020
    assert doc["emoji"] == "\U0001f600"
    roundtrip = safe_load(safe_dump(doc))
    assert roundtrip["emoji"] == "\U0001f600"
