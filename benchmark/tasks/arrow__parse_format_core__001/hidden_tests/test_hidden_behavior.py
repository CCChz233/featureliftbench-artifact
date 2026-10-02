from __future__ import annotations

import re
from pathlib import Path

from featurelifted import get


def test_format_literal_brackets() -> None:
    a = get("2020-01-15T12:30:00+00:00")
    assert a.format("YYYY [MM] DD") == "2020 MM 15"


def test_humanize_relative_hours() -> None:
    a = get("2020-01-15T12:30:00+00:00")
    other = get("2020-01-15T10:00:00+00:00")
    assert a.humanize(other) == "in 2 hours"


def test_parse_ordinal_day_token() -> None:
    a = get("January 5th 2020", "MMMM Do YYYY")
    assert a.year == 2020
    assert a.month == 1
    assert a.day == 5


def test_parse_lowercase_month() -> None:
    a = get("jan 15 2020", "MMM D YYYY")
    assert a.month == 1
    assert a.day == 15


def test_humanize_past_tense() -> None:
    a = get("2020-01-15T10:00:00+00:00")
    other = get("2020-01-15T12:30:00+00:00")
    assert a.humanize(other) == "2 hours ago"


def test_no_arrow_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from arrow|import arrow)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
