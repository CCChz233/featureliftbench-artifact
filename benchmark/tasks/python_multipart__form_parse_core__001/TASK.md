# FeatureLift Task: Multipart form-data parse core

Extract a task-scoped subset of `python_multipart` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    create_form_parser,
    exceptions,
    Field,
    File,
    FormParser,
    parse_form,
    parse_options_header,
)
```

## Required API Details

- `Field(name: 'bytes | None', *, content_type: 'str | None' = None) -> 'None'` class constructor
- `File(file_name: 'bytes | None', field_name: 'bytes | None' = None, config: 'FileConfig' = {}, *, content_type: 'str | None' = None) -> 'None'` class constructor
- `FormParser(content_type: 'str', on_field: 'Callable[[Field], None] | None', on_file: 'Callable[[File], None] | None', on_end: 'Callable[[], None] | None' = None, boundary: 'bytes | str | None' = None, file_name: 'bytes | None' = None, config: 'dict[Any, Any]' = {}) -> 'None'` class constructor
  - `FormParser.write(self, data: 'bytes') -> 'int'`
  - `FormParser.finalize(self) -> 'None'`
- `parse_form(headers: 'dict[str, bytes]', input_stream: 'SupportsRead', on_field: 'Callable[[Field], None] | None', on_file: 'Callable[[File], None] | None', chunk_size: 'int' = 1048576) -> 'None'`
- `create_form_parser(headers: 'dict[str, bytes]', on_field: 'Callable[[Field], None] | None', on_file: 'Callable[[File], None] | None', config: 'dict[Any, Any]' = {}) -> 'FormParser'`
- `parse_options_header(value: 'str | bytes | None') -> 'tuple[bytes, dict[bytes, bytes]]'`
- `exceptions` module must be importable
  - `exceptions.FormParserError` must be importable and raisable
  - `exceptions.MultipartParseError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: incremental multipart/form-data parsing via FormParser.write/finalize. Required observable cases include parse form helper; create form parser from headers; incremental chunked parsing.
- The extracted feature must support this observable behavior: field and file parts with Content-Disposition, Content-Type, and filename. Required observable cases include parse simple text field; missing field name raises.
- The extracted feature must support this observable behavior: parse_options_header boundary extraction from Content-Type. Required observable cases include parse simple text field; parse options header boundary; parse form helper; preamble before first boundary.
- The extracted feature must support this observable behavior: base64 and quoted-printable Content-Transfer-Encoding. Required observable cases include base64 content transfer encoding.
- The extracted feature must support this observable behavior: preamble before first boundary and epilogue after closing boundary. Required observable cases include preamble before first boundary; epilogue after closing boundary.
- The extracted feature must support this observable behavior: MAX_MEMORY_FILE_SIZE spill to disk and configurable upload directory. Required observable cases include parse file upload metadata; max memory file size spills to disk; max header size exceeded.
- The extracted feature must support this observable behavior: MAX_HEADER_COUNT and MAX_HEADER_SIZE enforcement. Required observable cases include max header size exceeded.
- The package exposes the required task API paths `featurelifted.Field`, `featurelifted.File`, `featurelifted.FormParser`, `featurelifted.FormParser.write`, `featurelifted.FormParser.finalize`, `featurelifted.parse_form`, `featurelifted.create_form_parser`, `featurelifted.parse_options_header`, `featurelifted.exceptions`, `featurelifted.exceptions.FormParserError`, `featurelifted.exceptions.MultipartParseError` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `python_multipart, multipart`.
- Do not implement application/x-www-form-urlencoded and application/octet-stream FormParser branches.
- Do not implement ASGI/Starlette/FastAPI request integration.
- Do not implement fuzz harness, upstream pytest suite, docs, and CI.
- Do not implement original python_multipart import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: incremental multipart/form-data parsing via FormParser.write/finalize. Required observable cases include parse form helper; create form parser from headers; incremental chunked parsing.
- **B002** — The extracted feature must support this observable behavior: field and file parts with Content-Disposition, Content-Type, and filename. Required observable cases include parse simple text field; missing field name raises.
- **B003** — The extracted feature must support this observable behavior: parse_options_header boundary extraction from Content-Type. Required observable cases include parse simple text field; parse options header boundary; parse form helper; preamble before first boundary.
- **B004** — The extracted feature must support this observable behavior: base64 and quoted-printable Content-Transfer-Encoding. Required observable cases include base64 content transfer encoding.
- **B005** — The extracted feature must support this observable behavior: preamble before first boundary and epilogue after closing boundary. Required observable cases include preamble before first boundary; epilogue after closing boundary.
- **B006** — The extracted feature must support this observable behavior: MAX_MEMORY_FILE_SIZE spill to disk and configurable upload directory. Required observable cases include parse file upload metadata; max memory file size spills to disk; max header size exceeded.
- **B007** — The extracted feature must support this observable behavior: MAX_HEADER_COUNT and MAX_HEADER_SIZE enforcement. Required observable cases include max header size exceeded.
- **B008** — The package exposes the required task API paths `featurelifted.Field`, `featurelifted.File`, `featurelifted.FormParser`, `featurelifted.FormParser.write`, `featurelifted.FormParser.finalize`, `featurelifted.parse_form`, `featurelifted.create_form_parser`, `featurelifted.parse_options_header`, `featurelifted.exceptions`, `featurelifted.exceptions.FormParserError`, `featurelifted.exceptions.MultipartParseError` with the kinds and callable signatures listed in this contract.
- **B009** — the submitted package does not import forbidden upstream packages: python_multipart, multipart.
<!-- featureliftbench:behavior-clauses:end -->
