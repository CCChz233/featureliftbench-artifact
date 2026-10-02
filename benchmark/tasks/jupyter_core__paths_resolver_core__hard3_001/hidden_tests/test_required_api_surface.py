"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    jupyter_config_dir,
    jupyter_config_path,
    jupyter_data_dir,
    jupyter_path,
    jupyter_runtime_dir,
)


def test_required_api_surface():
    assert callable(jupyter_config_dir)
    assert callable(jupyter_config_path)
    assert callable(jupyter_data_dir)
    assert callable(jupyter_path)
    assert callable(jupyter_runtime_dir)
