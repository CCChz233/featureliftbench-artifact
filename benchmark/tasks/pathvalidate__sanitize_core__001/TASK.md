# FeatureLift Task: Filename and filepath sanitization core

Extract a task-scoped subset of `pathvalidate` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    ErrorReason,
    InvalidCharError,
    is_valid_filename,
    is_valid_filepath,
    Platform,
    ReservedNameError,
    sanitize_filename,
    sanitize_filepath,
    validate_filename,
    validate_filepath,
    ValidationError,
)
```

## Required API Details

- `Platform(*values)` class constructor
- `sanitize_filename(filename: ~PathType, replacement_text: str = '', platform: Optional[~PlatformType] = None, max_len: Optional[int] = 255, fs_encoding: Optional[str] = None, check_reserved: Optional[bool] = None, null_value_handler: Optional[Callable[[ValidationError], str]] = None, reserved_name_handler: Optional[Callable[[ValidationError], str]] = None, additional_reserved_names: Optional[collections.abc.Sequence[str]] = None, validate_after_sanitize: bool = False) -> ~PathType`
- `sanitize_filepath(file_path: ~PathType, replacement_text: str = '', platform: Optional[~PlatformType] = None, max_len: Optional[int] = None, fs_encoding: Optional[str] = None, check_reserved: Optional[bool] = None, null_value_handler: Optional[Callable[[ValidationError], str]] = None, reserved_name_handler: Optional[Callable[[ValidationError], str]] = None, additional_reserved_names: Optional[collections.abc.Sequence[str]] = None, normalize: bool = True, validate_after_sanitize: bool = False) -> ~PathType`
- `validate_filename(filename: ~PathType, platform: Optional[~PlatformType] = None, min_len: int = 1, max_len: int = 255, fs_encoding: Optional[str] = None, check_reserved: bool = True, additional_reserved_names: Optional[collections.abc.Sequence[str]] = None) -> None`
- `validate_filepath(file_path: ~PathType, platform: Optional[~PlatformType] = None, min_len: int = 1, max_len: Optional[int] = None, fs_encoding: Optional[str] = None, check_reserved: bool = True, additional_reserved_names: Optional[collections.abc.Sequence[str]] = None) -> None`
- `is_valid_filename(filename: ~PathType, platform: Optional[~PlatformType] = None, min_len: int = 1, max_len: Optional[int] = None, fs_encoding: Optional[str] = None, check_reserved: bool = True, additional_reserved_names: Optional[collections.abc.Sequence[str]] = None) -> bool`
- `is_valid_filepath(file_path: ~PathType, platform: Optional[~PlatformType] = None, min_len: int = 1, max_len: Optional[int] = None, fs_encoding: Optional[str] = None, check_reserved: bool = True, additional_reserved_names: Optional[collections.abc.Sequence[str]] = None) -> bool`
- `ValidationError` must be importable and raisable
- `ErrorReason(*values)` class constructor
  - `ErrorReason.INVALID_CHARACTER` attribute must exist on instances
  - `ErrorReason.RESERVED_NAME` attribute must exist on instances
- `ReservedNameError` must be importable and raisable
- `InvalidCharError` must be importable and raisable

## Required Behavior

- The extracted feature must support this observable behavior: sanitize_filename replaces invalid characters. Required observable cases include sanitize filename replaces invalid chars; validate filename accepts simple name; invalid character error reason.
- The extracted feature must support this observable behavior: sanitize_filepath sanitizes each path segment. Required observable cases include sanitize filepath joins segments; sanitize filepath reserved segment.
- The extracted feature must support this observable behavior: Windows reserved device names (CON, PRN, etc.) rejected or rewritten. Required observable cases include windows reserved name sanitize; windows reserved name validate raises.
- The extracted feature must support this observable behavior: ValidationError exposes ErrorReason and reserved_name metadata. Required observable cases include filepath reserved name metadata.
- The extracted feature must support this observable behavior: platform parameter selects Windows/Linux/macOS/universal rules. Required observable cases include windows reserved name validate raises.
- The package exposes the required task API paths `featurelifted.Platform`, `featurelifted.sanitize_filename`, `featurelifted.sanitize_filepath`, `featurelifted.validate_filename`, `featurelifted.validate_filepath`, `featurelifted.is_valid_filename`, `featurelifted.is_valid_filepath`, `featurelifted.ValidationError`, `featurelifted.ErrorReason`, `featurelifted.ErrorReason.INVALID_CHARACTER`, `featurelifted.ErrorReason.RESERVED_NAME`, `featurelifted.ReservedNameError`, and 1 listed members with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `pathvalidate`.
- Do not implement click and argparse CLI integrations.
- Do not implement LTSV label and symbol replacement helpers.
- Do not implement upstream test suite and docs.
- Do not implement original pathvalidate import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: sanitize_filename replaces invalid characters. Required observable cases include sanitize filename replaces invalid chars; validate filename accepts simple name; invalid character error reason.
- **B002** — The extracted feature must support this observable behavior: sanitize_filepath sanitizes each path segment. Required observable cases include sanitize filepath joins segments; sanitize filepath reserved segment.
- **B003** — The extracted feature must support this observable behavior: Windows reserved device names (CON, PRN, etc.) rejected or rewritten. Required observable cases include windows reserved name sanitize; windows reserved name validate raises.
- **B004** — The extracted feature must support this observable behavior: ValidationError exposes ErrorReason and reserved_name metadata. Required observable cases include filepath reserved name metadata.
- **B005** — The extracted feature must support this observable behavior: platform parameter selects Windows/Linux/macOS/universal rules. Required observable cases include windows reserved name validate raises.
- **B006** — The package exposes the required task API paths `featurelifted.Platform`, `featurelifted.sanitize_filename`, `featurelifted.sanitize_filepath`, `featurelifted.validate_filename`, `featurelifted.validate_filepath`, `featurelifted.is_valid_filename`, `featurelifted.is_valid_filepath`, `featurelifted.ValidationError`, `featurelifted.ErrorReason`, `featurelifted.ErrorReason.INVALID_CHARACTER`, `featurelifted.ErrorReason.RESERVED_NAME`, `featurelifted.ReservedNameError`, and 1 listed members with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: pathvalidate.
<!-- featureliftbench:behavior-clauses:end -->
