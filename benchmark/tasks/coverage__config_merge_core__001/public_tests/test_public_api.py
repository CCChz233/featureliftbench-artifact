from __future__ import annotations

import os
from pathlib import Path

from featurelifted import read_run_config


def test_read_run_config_from_coveragerc(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".coveragerc").write_text(
        "[run]\n"
        "branch = true\n"
        "include = alpha, beta\n"
        "omit = */tests/*\n"
        "source = src\n",
        encoding="utf-8",
    )

    config = read_run_config(config_file=True)

    assert config.branch is True
    assert config.run_include == ["alpha", "beta"]
    assert config.run_omit == ["*/tests/*"]
    assert config.source == ["src"]


def test_read_run_config_kwargs_override(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".coveragerc").write_text(
        "[run]\nbranch = false\ninclude = from_file\n",
        encoding="utf-8",
    )

    config = read_run_config(config_file=True, branch=True, run_include=["from_args"])

    assert config.branch is True
    assert config.run_include == ["from_args"]
