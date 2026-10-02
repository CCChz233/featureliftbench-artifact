
import json
from pathlib import Path

from featurelifted import ExtensionConfigStore, merge_extension_configs, recursive_update


def test_recursive_update_and_enable(tmp_path):
    target = {"ServerApp": {"jpserver_extensions": {"a": True}}}
    recursive_update(target, {"ServerApp": {"jpserver_extensions": {"b": True}}})
    assert target["ServerApp"]["jpserver_extensions"] == {"a": True, "b": True}

    store = ExtensionConfigStore(tmp_path)
    store.enable("demo")
    assert store.enabled("demo")
