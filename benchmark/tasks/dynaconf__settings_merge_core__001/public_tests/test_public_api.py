from __future__ import annotations

import os
import tempfile

from featurelifted import Dynaconf, object_merge


def test_object_merge_nested_dict() -> None:
    old = {"db": {"host": "localhost", "port": 5432}, "items": [1, 2]}
    new = {"db": {"port": 3306, "user": "root"}, "items": [3]}
    merged = object_merge(old, new)
    assert merged == {"db": {"host": "localhost", "port": 3306, "user": "root"}, "items": [1, 2, 3]}


def test_dynaconf_toml_and_env_override() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "settings.toml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('[default]\nHOST = "localhost"\nPORT = 5432\n')
        os.environ["FLB_PORT"] = "8080"
        settings = Dynaconf(
            settings_files=[path],
            environments=True,
            envvar_prefix="FLB",
            load_dotenv=False,
        )
        settings.setenv("default")
        assert settings.HOST == "localhost"
        assert settings.PORT == 8080
