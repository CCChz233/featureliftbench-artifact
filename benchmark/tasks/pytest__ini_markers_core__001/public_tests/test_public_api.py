from featurelifted import MarkerRegistry
from featurelifted import parse_linelist


def test_parse_multiline_markers() -> None:
    raw = """
        a1: web test
        a2: smoke
    """
    lines = parse_linelist(raw)
    reg = MarkerRegistry.from_lines(lines)
    assert reg.names() == ["a1", "a2"]
    assert reg.description("a1") == "web test"


def test_append_marker_line() -> None:
    reg = MarkerRegistry()
    reg.add_line("slow: slow tests")
    reg.add_line("fast")
    assert reg.description("slow") == "slow tests"
    assert reg.description("fast") == ""
