from __future__ import annotations

import re
from pathlib import Path

from featurelifted import checks, dumps, loads, parse


def test_extra_space_after_opening_delimiter() -> None:
    text = (
        "--- \n"
        "test: tester\n"
        "something: else\n"
        "---\n"
        "\n"
        "This file has an extra space on the opening line of the frontmatter."
    )
    post = loads(text)
    assert post["test"] == "tester"
    assert post["something"] == "else"
    assert "extra space" in post.content


def test_crlf_bytes_normalize() -> None:
    markdown_bytes = (
        b'---\r\ntitle: "my title"\r\ncontent_type: "post"\r\n---\r\n\r\n'
        b"write your content in markdown here"
    )
    loaded = loads(markdown_bytes, "utf-8")
    assert loaded["title"] == "my title"
    assert loaded.content.strip() == "write your content in markdown here"


def test_no_frontmatter_returns_empty_metadata() -> None:
    text = "I have no frontmatter."
    post = loads(text)
    assert post.metadata == {}
    assert post.content == text


def test_empty_frontmatter_block() -> None:
    text = "---\n---\n\nI have frontmatter but no metadata."
    post = loads(text)
    assert post.metadata == {}
    assert post.content == "I have frontmatter but no metadata."


def test_unicode_metadata_roundtrip() -> None:
    text = (
        '---\n'
        'title: "Let\'s try unicode"\n'
        "language: 中文\n"
        "---\n"
        "\n"
        "欢迎来到大连水产学院！"
    )
    post = loads(text)
    output = dumps(post)
    assert "中文" in output
    repost = loads(output)
    assert repost["language"] == "中文"
    assert repost.content == post.content


def test_parse_defaults_merge() -> None:
    text = "---\nauthor: bob\n---\n\nHello"
    metadata, content = parse(text, site="default-site")
    assert metadata["author"] == "bob"
    assert metadata["site"] == "default-site"
    assert content.strip() == "Hello"

    plain_metadata, plain_content = parse("plain body only", site="default-site")
    assert plain_metadata == {"site": "default-site"}
    assert plain_content == "plain body only"


def test_post_to_dict() -> None:
    post = loads("---\ntitle: X\n---\n\nbody")
    payload = post.to_dict()
    assert payload["title"] == "X"
    assert payload["content"] == "body"


def test_checks_detects_frontmatter() -> None:
    assert checks("---\nx: 1\n---\n\nbody") is True
    assert checks("plain text without frontmatter") is False
    assert checks("---\n---\n\nempty metadata block") is True


def test_custom_dump_delimiters() -> None:
    post = loads("---\ntitle: Hi\n---\n\nbody")
    dump = dumps(post, start_delimiter="+++", end_delimiter="+++")
    assert dump.startswith("+++")
    assert dump.count("+++") >= 2
    assert "title: Hi" in dump
    assert dump.strip().endswith("body")


def test_no_frontmatter_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(
        r"^\s*(?:from frontmatter|import frontmatter)\b",
        re.MULTILINE,
    )
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
