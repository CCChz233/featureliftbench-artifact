from __future__ import annotations

from textwrap import dedent

from featurelifted import ConfigObj


def test_parse_sections_and_values() -> None:
    cfg = dedent(
        """\
        title = FeatureLift
        [owner]
        name = Ada
        """
    )
    conf = ConfigObj(cfg.splitlines(), list_values=False)
    assert conf["title"] == "FeatureLift"
    assert conf["owner"]["name"] == "Ada"


def test_write_roundtrip_keys() -> None:
    conf = ConfigObj()
    conf["alpha"] = "1"
    conf["beta"] = "2"
    conf["group"] = {}
    conf["group"]["inner"] = "x"
    text = "\n".join(conf.write())
    again = ConfigObj(text.splitlines(), list_values=False)
    assert again["alpha"] == "1"
    assert again["beta"] == "2"
    assert again["group"]["inner"] == "x"


def test_scalar_order_metadata() -> None:
    conf = ConfigObj()
    conf["z"] = "1"
    conf["a"] = "2"
    assert conf.scalars == ["z", "a"]
