from __future__ import annotations

import os
from pathlib import Path

from featurelifted import read_run_config


def test_read_run_config_from_setup_cfg(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("setup.cfg").write_text(
        "[coverage:run]\n"
        "omit = one, two\n"
        "source_pkgs = pkg.a, pkg.b\n"
        "parallel = true\n",
        encoding="utf-8",
    )

    config = read_run_config(config_file=True)

    assert config.run_omit == ["one", "two"]
    assert config.source_pkgs == ["pkg.a", "pkg.b"]
    assert config.parallel is True


def test_read_run_config_env_data_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COVERAGE_FILE", "custom.dat")
    Path(".coveragerc").write_text(
        "[run]\ndata_file = .coverage\n",
        encoding="utf-8",
    )

    config = read_run_config(config_file=True)

    assert config.data_file == "custom.dat"


def test_read_run_config_multiline_lists(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".coveragerc").write_text(
        "[run]\n"
        "include =\n"
        "    first,\n"
        "    second\n"
        "    third\n",
        encoding="utf-8",
    )

    config = read_run_config(config_file=True)

    assert config.run_include == ["first", "second", "third"]


def test_read_run_config_relative_files_section(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".coveragerc").write_text(
        "[run]\n"
        "relative_files = true\n"
        "disable_warnings = no-data-collected\n",
        encoding="utf-8",
    )

    config = read_run_config(config_file=True)

    assert config.relative_files is True
    assert "no-data-collected" in config.disable_warnings
