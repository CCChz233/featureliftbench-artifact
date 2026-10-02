import pytest

from featurelifted import ProfileDoesNotExist, UnsupportedSettings, resolve_settings, should_skip


def test_extend_skip_glob_and_existing_file_not_skipped(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    target = tmp_path / "pkg" / "client.py"
    target.parent.mkdir()
    target.write_text("import os\n", encoding="utf-8")
    pyproject.write_text(
        "[tool.isort]\nprofile='black'\nextend_skip_glob=['generated/*.py']\n",
        encoding="utf-8",
    )
    settings = resolve_settings([pyproject])

    assert should_skip(tmp_path / "generated" / "client.py", settings)
    assert not should_skip(target, settings)


def test_src_paths_are_resolved_relative_to_config_dir(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "lib").mkdir()
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.isort]\nsrc_paths=['src', 'lib']\n", encoding="utf-8")

    settings = resolve_settings([pyproject])

    assert settings.src_paths == ((tmp_path / "src").resolve(), (tmp_path / "lib").resolve())


def test_setup_cfg_and_pyproject_precedence_follows_input_order(tmp_path):
    setup_cfg = tmp_path / "setup.cfg"
    pyproject = tmp_path / "pyproject.toml"
    setup_cfg.write_text("[isort]\nline_length=90\n", encoding="utf-8")
    pyproject.write_text("[tool.isort]\nline_length=110\n", encoding="utf-8")

    assert resolve_settings([setup_cfg, pyproject]).line_length == 110
    assert resolve_settings([pyproject, setup_cfg]).line_length == 90


def test_invalid_profile_and_unsupported_setting_errors(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.isort]\nprofile='black'\n", encoding="utf-8")

    with pytest.raises(ProfileDoesNotExist):
        resolve_settings([pyproject], profile="does-not-exist")
    with pytest.raises(UnsupportedSettings):
        resolve_settings([pyproject], overrides={"not_an_isort_option": True})


def test_editorconfig_indent_and_line_length(tmp_path):
    editorconfig = tmp_path / ".editorconfig"
    editorconfig.write_text("[*.py]\nindent_style = space\nindent_size = 2\nmax_line_length = 99\n", encoding="utf-8")

    settings = resolve_settings([editorconfig])

    assert settings.line_length == 99
