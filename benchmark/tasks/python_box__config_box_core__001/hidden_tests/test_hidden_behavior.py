from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import ConfigBox
from featurelifted.exceptions import BoxKeyError


def test_case_insensitive_key_lookup() -> None:
    cfg = ConfigBox(my_flag="yes")
    assert cfg.bool("MY_FLAG") is True


def test_list_with_mod_callback() -> None:
    cfg = ConfigBox(items="1, 2, 3")
    assert cfg.list("items", mod=lambda x: int(x.strip())) == [1, 2, 3]


def test_float_and_getfloat_default() -> None:
    cfg = ConfigBox(rate="2.5")
    assert cfg.float("rate") == 2.5
    assert cfg.getfloat("missing", 1.5) == 1.5


def test_getboolean_alias() -> None:
    cfg = ConfigBox(flag="false")
    assert cfg.getboolean("flag") is False


def test_missing_key_raises() -> None:
    cfg = ConfigBox()
    with pytest.raises(BoxKeyError):
        cfg.int("missing")


def test_no_box_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from box|import box)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
