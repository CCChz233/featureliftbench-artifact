from __future__ import annotations

from featurelifted import tabulate, tabulate_formats


def test_tabulate_simple_ascii() -> None:
    result = tabulate([[1, 2.34], [-56, "8.999"]])
    lines = result.splitlines()
    assert lines[0].startswith("---")
    assert "1" in lines[1] and "2.34" in lines[1]
    assert "-56" in lines[2] and "8.999" in lines[2]
    assert lines[-1].startswith("---")


def test_tabulate_with_headers() -> None:
    result = tabulate(
        [["Alice", 24], ["Bob", 19]],
        headers=["Name", "Age"],
        tablefmt="simple",
    )
    lines = result.splitlines()
    assert lines[0].startswith("Name") and "Age" in lines[0]
    assert "Alice" in lines[2] and "24" in lines[2]
    assert "Bob" in lines[3] and "19" in lines[3]


def test_tabulate_grid_basic() -> None:
    result = tabulate([["a", "b"], ["c", "d"]], tablefmt="grid")
    assert result == "+---+---+\n| a | b |\n+---+---+\n| c | d |\n+---+---+"


def test_tabulate_formats_registry() -> None:
    assert "simple" in tabulate_formats
    assert "grid" in tabulate_formats
    assert "pipe" in tabulate_formats
    assert len(tabulate_formats) >= 30
