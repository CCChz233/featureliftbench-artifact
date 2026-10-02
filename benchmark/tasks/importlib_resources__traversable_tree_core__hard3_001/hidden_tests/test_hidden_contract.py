import importlib
import sys

import pytest

from featurelifted import MemoryTraversable, TraversalError, files, read_binary, read_text


def make_package(tmp_path):
    package = tmp_path / "respkg"
    nested = package / "nested" / "inner"
    nested.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "root.txt").write_text("root", encoding="utf-8")
    (nested / "utf16.txt").write_text("snowman", encoding="utf-16")
    (nested / "data.bin").write_bytes(bytes(range(5)))
    sys.path.insert(0, str(tmp_path))
    try:
        return importlib.import_module("respkg")
    finally:
        sys.path.remove(str(tmp_path))


def test_nested_joinpath_accepts_multiple_segments(tmp_path):
    package = make_package(tmp_path)
    resource = files(package).joinpath("nested", "inner", "data.bin")

    assert resource.name == "data.bin"
    assert resource.is_file()
    assert resource.read_bytes() == bytes(range(5))


def test_text_encoding_and_binary_open_are_preserved(tmp_path):
    package = make_package(tmp_path)
    root = files(package)

    assert root.joinpath("nested/inner/utf16.txt").read_text(encoding="utf-16") == "snowman"
    with root.joinpath("nested/inner/data.bin").open("rb") as stream:
        assert stream.read() == bytes(range(5))


def test_parent_traversal_is_rejected(tmp_path):
    package = make_package(tmp_path)

    with pytest.raises(TraversalError):
        files(package).joinpath("nested", "..", "__init__.py")
    with pytest.raises(TraversalError):
        read_text(package, "../pyproject.toml")


def test_memory_traversable_matches_filesystem_contract():
    tree = MemoryTraversable.directory(
        "root",
        {
            "docs": {
                "intro.txt": "hello",
                "payload.bin": b"\x10\x20",
            }
        },
    )

    assert files(tree).joinpath("docs").is_dir()
    assert read_text(tree, "docs/intro.txt") == "hello"
    assert read_binary(tree, "docs/payload.bin") == b"\x10\x20"


def test_missing_resource_raises_traversal_error(tmp_path):
    package = make_package(tmp_path)

    with pytest.raises(TraversalError):
        files(package).joinpath("nested", "missing.txt")
