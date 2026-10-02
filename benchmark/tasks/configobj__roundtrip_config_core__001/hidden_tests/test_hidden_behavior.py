from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest

from featurelifted import ConfigObj, DuplicateError, flatten_errors, get_extra_values
from featurelifted.validate import Validator, VdtValueTooSmallError


def test_comment_preserved_on_write() -> None:
    cfg = dedent(
        """\
        # banner
        name = Ada
        """
    )
    conf = ConfigObj(cfg.splitlines(), list_values=False)
    out = "\n".join(conf.write())
    assert "# banner" in out
    assert "name = Ada" in out


def test_configspec_validation_failure_flattened() -> None:
    cfg = "port = 3\n"
    spec = "port = integer(min=10)\n"
    conf = ConfigObj(cfg.splitlines(), configspec=spec.splitlines())
    validator = Validator()
    result = conf.validate(validator)
    assert result is False
    flat = flatten_errors(conf, result)
    assert flat
    assert any(item[2] is False for item in flat)


def test_duplicate_section_raises() -> None:
    cfg = dedent(
        """\
        [a]
        x = 1
        [a]
        y = 2
        """
    )
    with pytest.raises(DuplicateError):
        ConfigObj(cfg.splitlines())


def test_get_extra_values_from_configspec() -> None:
    cfg = dedent(
        """\
        known = 1
        extra = 2
        """
    )
    spec = "known = integer\n"
    conf = ConfigObj(cfg.splitlines(), configspec=spec.splitlines())
    validator = Validator()
    conf.validate(validator)
    extras = get_extra_values(conf)
    names = [name for _path, name in extras]
    assert "extra" in names


def test_configparser_interpolation_resolves() -> None:
    cfg = dedent(
        """\
        name = World
        greeting = Hello %(name)s
        """
    )
    conf = ConfigObj(cfg.splitlines(), interpolation="configparser", list_values=False)
    assert conf["greeting"] == "Hello World"


def test_no_configobj_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from configobj|import configobj)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
