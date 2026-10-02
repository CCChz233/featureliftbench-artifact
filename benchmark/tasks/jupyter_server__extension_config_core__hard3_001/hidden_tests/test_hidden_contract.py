
import json
from pathlib import Path

from featurelifted import ExtensionConfigStore, filter_enabled_extensions, merge_extension_configs, recursive_update


def test_config_precedence_and_disable(tmp_path):
    root = tmp_path / "jupyter_server_config.json"
    root.write_text(json.dumps({"ServerApp": {"jpserver_extensions": {"a": True, "b": True}}}), encoding="utf-8")
    ddir = tmp_path / "jupyter_server_config.d"
    ddir.mkdir()
    (ddir / "b.json").write_text(json.dumps({"ServerApp": {"jpserver_extensions": {"b": False}}}), encoding="utf-8")

    store = ExtensionConfigStore(tmp_path)
    assert store.get_extensions() == {"a": True, "b": False}
    store.disable("a")
    assert store.enabled("a") is False

    merged = merge_extension_configs([root, ddir / "b.json"])
    assert merged["b"] is False


def test_filter_enabled_extensions_masks_disabled():
    eps = ["a", "b", "c"]
    cfg = {"a": True, "b": False}
    assert filter_enabled_extensions(eps, cfg) == ["a", "c"]


def test_recursive_update_prunes_empty_nested_dicts():
    target = {"ServerApp": {"jpserver_extensions": {"a": True}}}
    recursive_update(target, {"ServerApp": {"jpserver_extensions": {"a": None}}})
    assert "ServerApp" not in target or "jpserver_extensions" not in target.get("ServerApp", {})
