from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from featurelifted import CroniterBadCronError, croniter


BASE = datetime(2024, 1, 15, 12, 0, 0)


def test_step_and_range_fields() -> None:
    itr = croniter("*/15 9-17 * * *", BASE)
    assert itr.get_next(datetime) == datetime(2024, 1, 15, 12, 15, 0)
    assert itr.get_next(datetime) == datetime(2024, 1, 15, 12, 30, 0)


def test_invalid_minute_raises() -> None:
    with pytest.raises(CroniterBadCronError):
        croniter("99 12 * * *", BASE)


def test_combined_next_prev_walk() -> None:
    expr = "0 8,20 * * *"
    forward = croniter(expr, BASE)
    assert forward.get_next(datetime) == datetime(2024, 1, 15, 20, 0, 0)
    assert forward.get_next(datetime) == datetime(2024, 1, 16, 8, 0, 0)

    backward = croniter(expr, BASE)
    assert backward.get_prev(datetime) == datetime(2024, 1, 15, 8, 0, 0)
    assert backward.get_prev(datetime) == datetime(2024, 1, 14, 20, 0, 0)


def test_dom_dow_union_next() -> None:
    itr = croniter("0 12 15 * 1", BASE)
    assert itr.get_next(datetime) == datetime(2024, 1, 22, 12, 0, 0)


def test_no_croniter_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from croniter|import croniter)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
