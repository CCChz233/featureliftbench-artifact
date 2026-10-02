from __future__ import annotations

import os
import tempfile

from featurelifted import Dynaconf, object_merge


def test_object_merge_list_shallow() -> None:
    old = {"items": [1, 2, 3]}
    new = {"items": [9]}
    merged = object_merge(old, new, list_merge="shallow")
    assert merged["items"] == [9]


def test_object_merge_list_deep_path() -> None:
    old = {"groups": [{"ids": [1, 2]}]}
    new = {"groups": [{"ids": [3]}]}
    merged = object_merge(old, new, list_merge="deep", full_path=["groups", 0, "ids"])
    assert merged["groups"][0]["ids"] == [3]


def test_layered_toml_environments() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "settings.toml")
        with open(base, "w", encoding="utf-8") as fh:
            fh.write('[default]\nHOST = "localhost"\nPORT = 5432\n\n[development]\nPORT = 3000\n')
        settings = Dynaconf(
            settings_files=[base],
            environments=True,
            load_dotenv=False,
        )
        settings.setenv("development")
        assert settings.HOST == "localhost"
        assert settings.PORT == 3000


def test_merge_multiple_settings_files() -> None:
    with tempfile.TemporaryDirectory() as td:
        a = os.path.join(td, "a.toml")
        b = os.path.join(td, "b.toml")
        open(a, "w").write('[default]\nFOO = 1\nLIST = [1,2]\n')
        open(b, "w").write('[default]\nBAR = 2\n')
        settings = Dynaconf(
            settings_files=[a, b],
            environments=True,
            load_dotenv=False,
            merge_enabled=True,
        )
        settings.setenv("default")
        assert settings.FOO == 1
        assert settings.BAR == 2
        assert settings.LIST == [1, 2]
