from featurelifted import MarkerRegistry
from featurelifted import parse_linelist
from featurelifted import split_marker_line


def test_linelist_strips_blank_lines() -> None:
    assert parse_linelist("a\nb\n\n c ") == ["a", "b", "c"]


def test_split_marker_line_whitespace() -> None:
    name, desc = split_marker_line("  a1 :  whitespace marker  ")
    assert name == "a1"
    assert desc == "  whitespace marker  "


def test_registry_module_order_preserved() -> None:
    reg = MarkerRegistry.from_ini(["z: last", "a: first"])
    assert reg.names() == ["z", "a"]
