# FeatureLift Task: Dotenv parse and set_key core

Extract a task-scoped subset of `dotenv` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    dotenv_values,
    get_key,
    set_key,
)
```

## Required API Details

- `dotenv_values(dotenv_path: Union[str, ForwardRef('os.PathLike[str]'), NoneType] = None, stream: Optional[IO[str]] = None, verbose: bool = False, interpolate: bool = True, encoding: Optional[str] = 'utf-8') -> Dict[str, Optional[str]]`
- `set_key(dotenv_path: Union[str, ForwardRef('os.PathLike[str]')], key_to_set: str, value_to_set: str, quote_mode: str = 'always', export: bool = False, encoding: Optional[str] = 'utf-8', follow_symlinks: bool = False) -> Tuple[Optional[bool], str, str]`
- `get_key(dotenv_path: Union[str, ForwardRef('os.PathLike[str]')], key_to_get: str, encoding: Optional[str] = 'utf-8') -> Optional[str]`

## Required Behavior

- The extracted feature must support this observable behavior: parse key=value pairs from stream with export prefix and comments. Required observable cases include dotenv values simple pairs; dotenv values export prefix; inline comment after whitespace; key without value is none.
- The extracted feature must support this observable behavior: single- and double-quoted values with escape sequences. Required observable cases include dotenv values quoted value; double quote escape sequences; single quote escape only backslash and quote.
- The extracted feature must support this observable behavior: UTF-8 BOM stripping at file start. Required observable cases include utf8 bom stripped.
- The extracted feature must support this observable behavior: POSIX ${VAR} and ${VAR:-default} variable interpolation. Required observable cases include variable interpolation chain; variable default when missing.
- The extracted feature must support this observable behavior: set_key creates or updates keys with auto-quoting. Required observable cases include set key creates file; set key updates existing; set key quotes special characters; set key appends without trailing newline.
- The package exposes the required task API paths `featurelifted.dotenv_values`, `featurelifted.set_key`, `featurelifted.get_key` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `dotenv`.
- Do not implement CLI and IPython extension entrypoints.
- Do not implement load_dotenv os.environ side effects in hidden tests.
- Do not implement upstream test suite and docs.
- Do not implement original dotenv import at runtime.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: parse key=value pairs from stream with export prefix and comments. Required observable cases include dotenv values simple pairs; dotenv values export prefix; inline comment after whitespace; key without value is none.
- **B002** — The extracted feature must support this observable behavior: single- and double-quoted values with escape sequences. Required observable cases include dotenv values quoted value; double quote escape sequences; single quote escape only backslash and quote.
- **B003** — The extracted feature must support this observable behavior: UTF-8 BOM stripping at file start. Required observable cases include utf8 bom stripped.
- **B004** — The extracted feature must support this observable behavior: POSIX ${VAR} and ${VAR:-default} variable interpolation. Required observable cases include variable interpolation chain; variable default when missing.
- **B005** — The extracted feature must support this observable behavior: set_key creates or updates keys with auto-quoting. Required observable cases include set key creates file; set key updates existing; set key quotes special characters; set key appends without trailing newline.
- **B006** — The package exposes the required task API paths `featurelifted.dotenv_values`, `featurelifted.set_key`, `featurelifted.get_key` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: dotenv.
<!-- featureliftbench:behavior-clauses:end -->
