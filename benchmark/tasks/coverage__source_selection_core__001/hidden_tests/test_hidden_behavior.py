from __future__ import annotations

import os

from featurelifted import SourceSelector


def test_source_selector_package_name(tmp_path) -> None:
    src = tmp_path / "src"
    pkg = src / "mypkg"
    pkg.mkdir(parents=True)
    module = pkg / "mod.py"
    module.write_text("value = 1\n", encoding="utf-8")

    selector = SourceSelector(source_pkgs=["mypkg"])

    assert selector.skip_reason(str(module), modulename="mypkg.mod") is None
    assert selector.skip_reason(str(module), modulename="other.mod") is not None


def test_source_selector_include_without_source(tmp_path) -> None:
    include_root = tmp_path / "included"
    include_root.mkdir()
    included = include_root / "keep.py"
    included.write_text("a = 1\n", encoding="utf-8")
    skipped = tmp_path / "skip.py"
    skipped.write_text("b = 2\n", encoding="utf-8")

    selector = SourceSelector(run_include=[str(include_root / "*")])

    assert selector.skip_reason(str(included)) is None
    reason = selector.skip_reason(str(skipped))
    assert reason is not None
    assert "include" in reason


def test_source_selector_rejects_non_utf8_filename(tmp_path) -> None:
    selector = SourceSelector(cover_pylib=True)
    bad_name = str(tmp_path / "bad-\udcff-name.py")
    reason = selector.skip_reason(bad_name)
    assert reason is not None
    assert "non-encodable" in reason


def test_source_selector_omit_wins_over_include(tmp_path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    kept = root / "keep.py"
    kept.write_text("a = 1\n", encoding="utf-8")
    omitted = root / "skip.py"
    omitted.write_text("b = 2\n", encoding="utf-8")

    selector = SourceSelector(
        run_include=[str(root / "*.py")],
        run_omit=[str(omitted)],
    )

    assert selector.skip_reason(str(kept)) is None
    assert selector.skip_reason(str(omitted)) is not None
