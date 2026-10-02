from featurelifted import resolve_from_path, resolve_settings, should_skip


def test_profile_and_pyproject_merge(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.isort]\nprofile='black'\nskip=['build']\n", encoding="utf-8")

    settings = resolve_settings([pyproject])

    assert settings.profile == "black"
    assert settings.line_length == 88
    assert should_skip(tmp_path / "build" / "x.py", settings)
    assert settings.is_skipped(tmp_path / "build" / "x.py")


def test_runtime_overrides_win_over_profile_and_config(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.isort]\nprofile='black'\nline_length=100\n", encoding="utf-8")

    settings = resolve_settings([pyproject], overrides={"line_length": 120})

    assert settings.line_length == 120
    assert settings.include_trailing_comma is True


def test_resolve_from_path_finds_nearest_pyproject(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.isort]\nprofile='django'\n", encoding="utf-8")

    settings = resolve_from_path(package / "module.py")

    assert settings.profile == "django"
    assert settings.combine_as_imports is True
