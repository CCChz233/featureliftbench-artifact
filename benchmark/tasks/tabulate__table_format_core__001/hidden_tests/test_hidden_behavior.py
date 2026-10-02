from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import tabulate


def test_decimal_column_alignment() -> None:
    result = tabulate([[1.234], [2.3], [10.1]], tablefmt="plain", numalign="decimal")
    assert result == " 1.234\n 2.3\n10.1"


def test_wide_char_grid_alignment() -> None:
    wcwidth = pytest.importorskip("wcwidth")
    _ = wcwidth
    result = tabulate(
        [["한글", 1], ["en", 2]],
        headers=["word", "n"],
        tablefmt="grid",
    )
    assert "| 한글   |   1 |" in result
    assert "| en     |   2 |" in result


def test_colglobalalign_center_column() -> None:
    result = tabulate(
        [["a", 1], ["bbb", 2]],
        colglobalalign="center",
        colalign=("center", "right"),
        tablefmt="plain",
    )
    assert result == " a   1\nbbb  2"


def test_pipe_format_colalign() -> None:
    result = tabulate(
        [["left", 1], ["x", 2]],
        headers=["s", "n"],
        tablefmt="pipe",
        colalign=("left", "right"),
    )
    assert "|:-----|" in result
    assert "|----:|" in result
    assert "| left |   1 |" in result


def test_ansi_visible_width_plain() -> None:
    colored = "\x1b[31mred\x1b[0m"
    result = tabulate([[colored, "x"]], tablefmt="plain")
    assert result == f"{colored}  x"


def test_latex_booktabs_format() -> None:
    result = tabulate([[1, 2]], headers=["a", "b"], tablefmt="latex_booktabs")
    assert "\\toprule" in result
    assert "\\bottomrule" in result


def test_html_escapes_angle_brackets() -> None:
    result = tabulate([["<b>"]], tablefmt="html")
    assert "&lt;b&gt;" in result


def test_dict_rows_headers_keys() -> None:
    result = tabulate({"name": ["a"], "n": [1]}, headers="keys", tablefmt="simple")
    assert "name" in result and "a" in result


def test_no_tabulate_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from tabulate|import tabulate)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
