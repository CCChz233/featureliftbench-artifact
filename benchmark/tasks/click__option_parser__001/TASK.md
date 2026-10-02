# FeatureLift Task: Command line option parsing and invocation

Extract a task-scoped subset of `click` into a standalone `featurelifted` package.

The submitted implementation must not import the upstream package or read from `repo/` at runtime, must not use the network, and must not depend on external services. Use only the standard library unless the task lockfile allows otherwise.

## Target API

```python
from featurelifted import (
    testing,
)
```

## Required API Details

- `testing` module must be importable
  - `testing.CliRunner(charset: str = 'utf-8', env: Optional[Mapping[str, Optional[str]]] = None, echo_stdin: bool = False, mix_stderr: bool = True) -> None` class constructor
    - `testing.CliRunner.invoke(self, cli: 'BaseCommand', args: Union[Sequence[str], str, NoneType] = None, input: Union[str, bytes, IO[Any], NoneType] = None, env: Optional[Mapping[str, Optional[str]]] = None, catch_exceptions: bool = True, color: bool = False, **extra: Any) -> Result`
    - `testing.CliRunner.isolated_filesystem(self, temp_dir: Union[str, ForwardRef('os.PathLike[str]'), NoneType] = None) -> Iterator[str]`

## Required Behavior

- The extracted feature must support this observable behavior: decorate functions as commands and groups. Required observable cases include usage errors prompts and isolated filesystem.
- The extracted feature must support this observable behavior: parse options, flags, choices, defaults, integer ranges, and positional arguments. Required observable cases include command options arguments and choice errors; group context flags range and defaults.
- The extracted feature must support this observable behavior: invoke commands through CliRunner and capture output, exit code, and exceptions. Required observable cases include usage errors prompts and isolated filesystem.
- The extracted feature must support this observable behavior: support nested groups and context object passing. Required observable cases include usage errors prompts and isolated filesystem.
- The extracted feature must support this observable behavior: render useful usage/error output for invalid options and bad values. Required observable cases include usage errors prompts and isolated filesystem.
- The package exposes the required task API paths `featurelifted.testing`, `featurelifted.testing.CliRunner`, `featurelifted.testing.CliRunner.invoke`, `featurelifted.testing.CliRunner.isolated_filesystem` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `click`.
- Do not implement shell completion integration.
- Do not implement terminal color/style platform integrations beyond basic echo.
- Do not implement documentation and release tooling.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: decorate functions as commands and groups. Required observable cases include usage errors prompts and isolated filesystem.
- **B002** — The extracted feature must support this observable behavior: parse options, flags, choices, defaults, integer ranges, and positional arguments. Required observable cases include command options arguments and choice errors; group context flags range and defaults.
- **B003** — The extracted feature must support this observable behavior: invoke commands through CliRunner and capture output, exit code, and exceptions. Required observable cases include usage errors prompts and isolated filesystem.
- **B004** — The extracted feature must support this observable behavior: support nested groups and context object passing. Required observable cases include usage errors prompts and isolated filesystem.
- **B005** — The extracted feature must support this observable behavior: render useful usage/error output for invalid options and bad values. Required observable cases include usage errors prompts and isolated filesystem.
- **B006** — The package exposes the required task API paths `featurelifted.testing`, `featurelifted.testing.CliRunner`, `featurelifted.testing.CliRunner.invoke`, `featurelifted.testing.CliRunner.isolated_filesystem` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: click.
<!-- featureliftbench:behavior-clauses:end -->
