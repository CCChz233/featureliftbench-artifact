from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest

from featurelifted import Field, File, FormParser
from featurelifted.exceptions import FormParserError, MultipartParseError


def _collect(body: bytes, *, boundary: str = "boundary", config: dict | None = None) -> tuple[list[Field], list[File]]:
    fields: list[Field] = []
    files: list[File] = []
    parser = FormParser(
        "multipart/form-data",
        fields.append,
        files.append,
        boundary=boundary,
        config=config or {},
    )
    parser.write(body)
    parser.finalize()
    return fields, files


def test_incremental_chunked_parsing() -> None:
    fields: list[Field] = []
    files: list[File] = []
    parser = FormParser("multipart/form-data", fields.append, files.append, boundary="boundary")

    chunks = [
        b"--boundary\r\nContent-Disposition: form-",
        b"data; name=\"f\"\r\n\r\npart",
        b"ial\r\n--boundary--\r\n",
    ]
    for chunk in chunks:
        parser.write(chunk)
    parser.finalize()

    assert len(fields) == 1
    assert fields[0].value == b"partial"
    assert files == []


def test_base64_content_transfer_encoding() -> None:
    body = (
        b"----boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        b"Content-Type: text/plain\r\n"
        b"Content-Transfer-Encoding: base64\r\n"
        b"\r\n"
        b"VGVzdA==\r\n"
        b"----boundary--\r\n"
    )
    fields, files = _collect(body, boundary="--boundary")
    assert fields == []
    assert len(files) == 1
    files[0].file_object.seek(0)
    assert files[0].file_object.read() == b"Test"


def test_preamble_before_first_boundary() -> None:
    body = (
        b"\r\nignored preamble\r\n"
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="f.txt"\r\n'
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"payload\r\n"
        b"--boundary--\r\n"
    )
    fields, files = _collect(body)
    assert fields == []
    assert len(files) == 1
    files[0].file_object.seek(0)
    assert files[0].file_object.read() == b"payload"


def test_epilogue_after_closing_boundary() -> None:
    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="f.txt"\r\n'
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"hello\r\n"
        b"--boundary--" + b"-" * 5000 + b"\r\n"
    )
    fields, files = _collect(body)
    assert len(files) == 1
    files[0].file_object.seek(0)
    assert files[0].file_object.read() == b"hello"


def test_missing_field_name_raises() -> None:
    body = (
        b"----boundary\r\n"
        b"Content-Disposition: form-data;\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Test\r\n"
        b"----boundary--\r\n"
    )
    with pytest.raises(FormParserError, match="Field name not found"):
        _collect(body, boundary="--boundary")


def test_max_memory_file_size_spills_to_disk() -> None:
    with tempfile.TemporaryDirectory() as upload_dir:
        body = (
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="big.bin"\r\n'
            b"Content-Type: application/octet-stream\r\n"
            b"\r\n"
            b"0123456789\r\n"
            b"--boundary--\r\n"
        )
        fields, files = _collect(
            body,
            config={
                "UPLOAD_DIR": upload_dir,
                "UPLOAD_DELETE_TMP": False,
                "MAX_MEMORY_FILE_SIZE": 4,
            },
        )
        assert fields == []
        assert len(files) == 1
        uploaded = files[0]
        assert uploaded.in_memory is False
        assert uploaded.actual_file_name is not None
        path = uploaded.actual_file_name.decode()
        try:
            assert os.path.exists(path)
            with open(path, "rb") as fh:
                assert fh.read() == b"0123456789"
        finally:
            uploaded.close()
            if os.path.exists(path):
                os.unlink(path)


def test_max_header_size_exceeded() -> None:
    long_value = b"x" * 32
    body = (
        b"--boundary\r\n"
        b"Content-Disposition: form-data; name=\"f\"\r\n"
        + b"X-Custom: " + long_value + b"\r\n"
        b"\r\n"
        b"data\r\n"
        b"--boundary--\r\n"
    )
    with pytest.raises(MultipartParseError, match="Maximum header size exceeded"):
        _collect(body, config={"MAX_HEADER_SIZE": 16})


def test_no_python_multipart_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    pattern = re.compile(r"^\s*(?:from (?:python_multipart|multipart)|import (?:python_multipart|multipart))\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8"))
