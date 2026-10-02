import importlib
import sys

from featurelifted import files, read_binary, read_text


def make_package(tmp_path):
    package = tmp_path / "samplepkg"
    data = package / "data"
    data.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "plain.txt").write_text("hello", encoding="utf-8")
    (data / "config.json").write_text('{"enabled": true}', encoding="utf-8")
    (data / "blob.bin").write_bytes(b"\x00\x01payload")
    sys.path.insert(0, str(tmp_path))
    try:
        return importlib.import_module("samplepkg")
    finally:
        sys.path.remove(str(tmp_path))


def test_files_returns_traversable_for_package(tmp_path):
    package = make_package(tmp_path)

    root = files(package)

    assert root.is_dir()
    assert {"__init__.py", "data", "plain.txt"}.issubset(
        {child.name for child in root.iterdir()}
    )
    assert root.joinpath("plain.txt").is_file()
    assert root.joinpath("plain.txt").read_text() == "hello"


def test_read_text_and_binary_from_string_anchor(tmp_path):
    make_package(tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        assert read_text("samplepkg", "data/config.json") == '{"enabled": true}'
        assert read_binary("samplepkg", "data/blob.bin") == b"\x00\x01payload"
    finally:
        sys.path.remove(str(tmp_path))
