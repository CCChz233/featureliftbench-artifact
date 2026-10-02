# FeatureLift Task: Typer command parser and CLI runner

Extract a task-scoped subset of `typer` into a standalone `featurelifted` package.

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
    - `testing.CliRunner.invoke(self, app: Typer, args: Union[Sequence[str], str, NoneType] = None, input: Union[str, bytes, IO[Any], NoneType] = None, env: Optional[Mapping[str, Optional[str]]] = None, catch_exceptions: bool = True, color: bool = False, **extra: Any) -> Result`

## Required Behavior

- The extracted feature must support this observable behavior: build commands from type-annotated functions. Required observable cases include subcommands and optional path.
- The extracted feature must support this observable behavior: parse options, arguments, defaults, and choices. Required observable cases include typed options and arguments; subcommands and optional path.
- The extracted feature must support this observable behavior: invoke Typer apps through CliRunner. Required observable cases include typed options and arguments; subcommands and optional path; choice validation.
- The extracted feature must support this observable behavior: nested subcommands and context passing. Required observable cases include subcommands and optional path.
- The extracted feature must support this observable behavior: usage errors for invalid parameters. Required observable cases include subcommands and optional path.
- The package exposes the required task API paths `featurelifted.testing`, `featurelifted.testing.CliRunner`, `featurelifted.testing.CliRunner.invoke` with the kinds and callable signatures listed in this contract.

## Constraints

- Forbidden imports: `typer, click`.
- Do not implement shell completion integration.
- Do not implement rich markup rendering beyond basic echo.
- Do not implement documentation and release tooling.

## Public vs Hidden Tests

Benchmark evaluator tests remain private. Each evaluator test maps to the public behaviors above and only deepens examples, boundaries, or combinations within those declared behaviors.

<!-- featureliftbench:behavior-clauses:start -->
## Public Behavior Contract

The stable clause IDs below define the public behavior contract. Hidden tests may exercise these clauses but do not introduce additional requirements.

- **B001** — The extracted feature must support this observable behavior: build commands from type-annotated functions. Required observable cases include subcommands and optional path.
- **B002** — The extracted feature must support this observable behavior: parse options, arguments, defaults, and choices. Required observable cases include typed options and arguments; subcommands and optional path.
- **B003** — The extracted feature must support this observable behavior: invoke Typer apps through CliRunner. Required observable cases include typed options and arguments; subcommands and optional path; choice validation.
- **B004** — The extracted feature must support this observable behavior: nested subcommands and context passing. Required observable cases include subcommands and optional path.
- **B005** — The extracted feature must support this observable behavior: usage errors for invalid parameters. Required observable cases include subcommands and optional path.
- **B006** — The package exposes the required task API paths `featurelifted.testing`, `featurelifted.testing.CliRunner`, `featurelifted.testing.CliRunner.invoke` with the kinds and callable signatures listed in this contract.
- **B007** — the submitted package does not import forbidden upstream packages: typer, click.
<!-- featureliftbench:behavior-clauses:end -->
