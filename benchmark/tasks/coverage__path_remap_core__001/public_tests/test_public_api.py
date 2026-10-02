from __future__ import annotations

import os

import pytest

from featurelifted import PathAliases
from featurelifted.exceptions import ConfigError


def test_path_aliases_maps_wildcard_prefix() -> None:
    aliases = PathAliases(relative=False)
    aliases.add("/ned/home/*/src", "./mysrc")
    mapped = aliases.map("/ned/home/foo/src/a.py", exists=lambda _path: True)
    assert mapped.replace("\\", "/").endswith("mysrc/a.py")


def test_path_aliases_leaves_unmatched_paths() -> None:
    aliases = PathAliases(relative=False)
    aliases.add("/home/*/src", "./mysrc")
    original = "/home/foo/a.py"
    assert aliases.map(original, exists=lambda _path: True) == original
