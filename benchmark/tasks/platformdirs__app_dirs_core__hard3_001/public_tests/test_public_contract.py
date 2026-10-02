from featurelifted import user_cache_dir, user_config_dir, user_data_dir


def test_linux_defaults_append_app_and_version():
    assert user_data_dir("demo", version="2", platform="linux", home="/home/alice", env={}) == (
        "/home/alice/.local/share/demo/2"
    )
    assert user_config_dir("demo", platform="linux", home="/home/alice", env={}) == "/home/alice/.config/demo"
    assert user_cache_dir("demo", platform="linux", home="/home/alice", env={}) == "/home/alice/.cache/demo"


def test_linux_xdg_overrides_take_precedence():
    env = {
        "XDG_DATA_HOME": "/srv/data",
        "XDG_CONFIG_HOME": "/srv/config",
        "XDG_CACHE_HOME": "/srv/cache",
    }
    assert user_data_dir("tool", platform="linux", home="/home/alice", env=env) == "/srv/data/tool"
    assert user_config_dir("tool", platform="linux", home="/home/alice", env=env) == "/srv/config/tool"
    assert user_cache_dir("tool", platform="linux", home="/home/alice", env=env) == "/srv/cache/tool"


def test_windows_author_roaming_and_cache_layout():
    env = {
        "LOCALAPPDATA": r"C:\Users\Alice\AppData\Local",
        "APPDATA": r"C:\Users\Alice\AppData\Roaming",
    }
    assert user_data_dir("App", appauthor="Vendor", platform="windows", env=env) == (
        r"C:\Users\Alice\AppData\Local\Vendor\App"
    )
    assert user_data_dir("App", appauthor="Vendor", roaming=True, platform="windows", env=env) == (
        r"C:\Users\Alice\AppData\Roaming\Vendor\App"
    )
    assert user_cache_dir("App", appauthor="Vendor", version="1.0", platform="windows", env=env) == (
        r"C:\Users\Alice\AppData\Local\Vendor\App\Cache\1.0"
    )
