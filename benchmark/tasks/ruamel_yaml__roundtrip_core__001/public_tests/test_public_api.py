from __future__ import annotations

from featurelifted import YAML, CommentedMap


def test_roundtrip_basic_mapping() -> None:
    text = "a: 1\nb: two\n"
    yaml = YAML()
    data = yaml.load(text)
    assert data["a"] == 1
    assert data["b"] == "two"
    from io import StringIO
    stream = StringIO()
    yaml.dump(data, stream)
    assert stream.getvalue().strip() == text.strip()


def test_key_order_preserved() -> None:
    text = "z: 1\na: 2\n"
    data = YAML().load(text)
    assert list(data.keys()) == ["z", "a"]
