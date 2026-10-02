from featurelifted import user_cache_dir, user_config_dir, user_data_dir


def test_macos_defaults_and_xdg_precedence():
    assert user_data_dir("Notebook", platform="darwin", home="/Users/ada", env={}) == (
        "/Users/ada/Library/Application Support/Notebook"
    )
    assert user_config_dir("Notebook", version="7", platform="macos", home="/Users/ada", env={}) == (
        "/Users/ada/Library/Application Support/Notebook/7"
    )
    env = {"XDG_DATA_HOME": "/Volumes/xdg-data", "XDG_CONFIG_HOME": "/Volumes/xdg-config"}
    assert user_data_dir("Notebook", platform="macos", home="/Users/ada", env=env) == "/Volumes/xdg-data/Notebook"
    assert user_config_dir("Notebook", platform="macos", home="/Users/ada", env=env) == (
        "/Volumes/xdg-config/Notebook"
    )


def test_blank_xdg_values_are_ignored():
    env = {"XDG_DATA_HOME": "   ", "XDG_CONFIG_HOME": "", "XDG_CACHE_HOME": "\t"}
    assert user_data_dir("tool", version="v2", platform="linux", home="/home/bob", env=env) == (
        "/home/bob/.local/share/tool/v2"
    )
    assert user_config_dir("tool", platform="linux", home="/home/bob", env=env) == "/home/bob/.config/tool"
    assert user_cache_dir("tool", platform="linux", home="/home/bob", env=env) == "/home/bob/.cache/tool"


def test_windows_appauthor_false_omits_author_segment():
    env = {"LOCALAPPDATA": r"D:\Local", "APPDATA": r"D:\Roaming"}
    assert user_data_dir("App", appauthor=False, version="3", platform="win32", env=env) == r"D:\Local\App\3"
    assert user_config_dir("App", appauthor=False, roaming=True, platform="windows", env=env) == r"D:\Roaming\App"


def test_windows_cache_opinion_can_be_disabled():
    env = {"LOCALAPPDATA": r"C:\Local"}
    assert user_cache_dir("App", appauthor="Vendor", version="2", platform="windows", env=env, opinion=False) == (
        r"C:\Local\Vendor\App\2"
    )


def test_no_appname_returns_platform_base_dir():
    assert user_data_dir(platform="linux", home="/home/chris", env={}) == "/home/chris/.local/share"
    assert user_cache_dir(platform="macos", home="/Users/chris", env={}) == "/Users/chris/Library/Caches"
    assert user_data_dir(platform="windows", home=r"C:\Users\Chris", env={}) == (
        r"C:\Users\Chris\AppData\Local"
    )
