from __future__ import annotations

import os

import pytest

from featurelifted import PathAliases
from featurelifted.exceptions import ConfigError


def test_path_aliases_multiple_rules() -> None:
    aliases = PathAliases(relative=False)
    aliases.add("/home/*/src", "./mysrc")
    aliases.add("/lib/*/libsrc", "./mylib")

    assert aliases.map("/home/foo/src/a.py", exists=lambda _path: True).replace("\\", "/").endswith(
        "mysrc/a.py",
    )
    assert aliases.map("/lib/foo/libsrc/a.py", exists=lambda _path: True).replace("\\", "/").endswith(
        "mylib/a.py",
    )


@pytest.mark.parametrize("badpat", ["/ned/home/*", "/ned/home/*/", "/ned/home/*/*/"])
def test_path_aliases_rejects_trailing_wildcards(badpat: str) -> None:
    aliases = PathAliases()
    with pytest.raises(ConfigError, match="must not end with wildcards"):
        aliases.add(badpat, "fooey")


def test_path_aliases_skips_nonexistent_targets() -> None:
    aliases = PathAliases(relative=False)
    aliases.add("/ned/home/*/src", "./mysrc")
    original = "/ned/home/foo/src/a.py"
    assert aliases.map(original, exists=lambda _path: False) == original


def test_path_aliases_relative_pattern() -> None:
    aliases = PathAliases(relative=True)
    aliases.add(".tox/*/site-packages", "src")
    mapped = aliases.map(".tox/py314/site-packages/proj/a.py", exists=lambda _path: True)
    assert mapped.replace("\\", "/") == "src/proj/a.py"
