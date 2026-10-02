from featurelifted import jupyter_config_dir, jupyter_config_path, jupyter_path, jupyter_runtime_dir


def test_hidden_runtime_dir_env_override_and_xdg_fallback():
    env = {
        "JUPYTER_PATH": "/one:/two",
        "XDG_DATA_HOME": "/xdg/data",
        "JUPYTER_RUNTIME_DIR": "/runtime",
    }
    assert jupyter_path(env=env, home="/home/a", platform="linux")[:2] == ["/one", "/two"]
    assert jupyter_runtime_dir(env=env, home="/home/a", platform="linux") == "/runtime"


def test_hidden_prefer_environment_over_user_changes_order():
    env = {"JUPYTER_PREFER_ENV_PATH": "yes"}
    paths = jupyter_config_path(env=env, home="/home/a", platform="linux", sys_prefix="/opt/venv")
    assert paths[:3] == ["/opt/venv/etc/jupyter", "/home/a/.jupyter", "/home/a/.local/etc/jupyter"]


def test_hidden_no_config_uses_clean_config_dir_only():
    env = {"JUPYTER_NO_CONFIG": "1", "JUPYTER_CONFIG_PATH": "/ignored"}
    assert jupyter_config_dir(env=env, home="/home/a", platform="linux") == "__JUPYTER_NO_CONFIG_TEMP__"
    assert jupyter_config_path(env=env, home="/home/a", platform="linux") == ["__JUPYTER_NO_CONFIG_TEMP__"]


def test_hidden_windows_path_separator_and_programdata_default():
    env = {"JUPYTER_PATH": r"C:\one;C:\two"}
    paths = jupyter_path(env=env, home=r"C:\Users\A", platform="win32", sys_prefix=r"C:\Py")
    assert paths[:2] == [r"C:\one", r"C:\two"]
    assert r"C:\Py\share\jupyter" in paths
    assert "/usr/share/jupyter" not in paths
