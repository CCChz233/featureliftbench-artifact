from __future__ import annotations

from featurelifted import dumps, loads, parse


def test_loads_yaml_frontmatter() -> None:
    text = "---\ntitle: Hello\nlayout: post\n---\n\nBody here."
    post = loads(text)
    assert post["title"] == "Hello"
    assert post["layout"] == "post"
    assert post.content.strip() == "Body here."


def test_dumps_roundtrip_metadata_and_body() -> None:
    text = "---\ntitle: Demo\n---\n\nKeep this line."
    post = loads(text)
    roundtrip = loads(dumps(post))
    assert roundtrip.metadata == post.metadata
    assert roundtrip.content == post.content


def test_parse_returns_metadata_and_content() -> None:
    text = "---\ncount: 1\n---\n\ncontent block"
    metadata, content = parse(text)
    assert metadata["count"] == 1
    assert content.strip() == "content block"
