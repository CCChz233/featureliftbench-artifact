from pathlib import Path

from featureliftbench.go_evaluator import _copy_runtime_with_tests
from featureliftbench.go_evaluator import _go_env


def test_go_env_uses_writable_tmp_cache_paths() -> None:
    env = _go_env()
    assert env["HOME"].startswith("/tmp/")
    assert env["GOCACHE"].startswith("/tmp/")
    assert env["GOMODCACHE"].startswith("/tmp/")
    assert env["TMPDIR"] == "/tmp"


def test_copy_runtime_with_tests_places_external_package_tests_in_subdir(tmp_path: Path) -> None:
    base = tmp_path / "base"
    tests = tmp_path / "tests"
    target = tmp_path / "target"
    base.mkdir()
    tests.mkdir()
    (base / "feature.go").write_text("package featurelifted\n", encoding="utf-8")
    (tests / "public_test.go").write_text("package publictests\n", encoding="utf-8")

    _copy_runtime_with_tests(base, tests, target, prefix="public")

    assert (target / "feature.go").is_file()
    assert (target / "flb_public_tests" / "0_public_test.go").is_file()
    assert not (target / "public_0_public_test.go").exists()
