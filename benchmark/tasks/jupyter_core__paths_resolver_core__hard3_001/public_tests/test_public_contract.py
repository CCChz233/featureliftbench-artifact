from featurelifted import jupyter_config_path, jupyter_data_dir, jupyter_path


def test_config_env_path_precedes_user_path():
    env = {"JUPYTER_CONFIG_PATH": "/env/etc:/more/etc"}
    paths = jupyter_config_path(env=env, home="/home/alice", platform="linux")
    assert paths[:2] == ["/env/etc", "/more/etc"]
    assert "/home/alice/.jupyter" in paths
    assert "/usr/etc/jupyter" in paths


def test_data_path_adds_requested_subdir():
    env = {"XDG_DATA_HOME": "/xdg/data"}
    paths = jupyter_path("kernels", env=env, home="/home/alice", platform="linux")
    assert paths[0] == "/xdg/data/jupyter/kernels"
    assert paths[-2:] == [
        "/usr/local/share/jupyter/kernels",
        "/usr/share/jupyter/kernels",
    ]


def test_data_dir_platform_defaults():
    assert jupyter_data_dir(env={}, home="/Users/alice", platform="darwin") == "/Users/alice/Library/Jupyter"
    assert jupyter_data_dir(env={"APPDATA": r"C:\Users\Alice\AppData\Roaming"}, home=r"C:\Users\Alice", platform="win32") == r"C:\Users\Alice\AppData\Roaming\jupyter"
