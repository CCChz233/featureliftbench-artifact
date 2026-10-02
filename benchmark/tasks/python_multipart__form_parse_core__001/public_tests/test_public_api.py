from __future__ import annotations

from io import BytesIO

from featurelifted import Field, File, FormParser, create_form_parser, parse_form, parse_options_header


def _parse_multipart(body: bytes, boundary: str = "boundary") -> tuple[list[Field], list[File]]:
    fields: list[Field] = []
    files: list[File] = []

    parser = FormParser(
        "multipart/form-data",
        fields.append,
        files.append,
        boundary=boundary,
    )
    parser.write(body)
    parser.finalize()
    return fields, files


def test_parse_simple_text_field() -> None:
    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="username"\r\n'
        b"\r\n"
        b"alice\r\n"
        b"--boundary--\r\n"
    )
    fields, files = _parse_multipart(body)
    assert files == []
    assert len(fields) == 1
    assert fields[0].field_name == b"username"
    assert fields[0].value == b"alice"


def test_parse_file_upload_metadata() -> None:
    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="upload"; filename="note.txt"\r\n'
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"hello file\r\n"
        b"--boundary--\r\n"
    )
    fields, files = _parse_multipart(body)
    assert fields == []
    assert len(files) == 1
    uploaded = files[0]
    assert uploaded.field_name == b"upload"
    assert uploaded.file_name == b"note.txt"
    assert uploaded.content_type == "text/plain"
    uploaded.file_object.seek(0)
    assert uploaded.file_object.read() == b"hello file"


def test_parse_options_header_boundary() -> None:
    ctype, params = parse_options_header("multipart/form-data; boundary=----abc")
    assert ctype == b"multipart/form-data"
    assert params[b"boundary"] == b"----abc"


def test_parse_form_helper() -> None:
    body = (
        b"--b\r\n"
        b'Content-Disposition: form-data; name="k"\r\n'
        b"\r\n"
        b"v\r\n"
        b"--b--\r\n"
    )
    headers = {"Content-Type": "multipart/form-data; boundary=b"}
    fields: list[Field] = []
    files: list[File] = []

    parse_form(headers, BytesIO(body), fields.append, files.append)

    assert len(fields) == 1
    assert fields[0].value == b"v"
    assert files == []


def test_create_form_parser_from_headers() -> None:
    headers = {"Content-Type": "multipart/form-data; boundary=xyz"}
    fields: list[Field] = []
    parser = create_form_parser(headers, fields.append, None)
    parser.write(
        b"--xyz\r\n"
        b'Content-Disposition: form-data; name="a"\r\n'
        b"\r\n"
        b"1\r\n"
        b"--xyz--\r\n"
    )
    parser.finalize()
    assert fields[0].field_name == b"a"
