from __future__ import annotations

import featurelifted as typer
from featurelifted.testing import CliRunner


def test_typed_options_and_arguments() -> None:
    app = typer.Typer()

    @app.command()
    def greet(name: str, count: int = 1, formal: bool = False):
        prefix = "Hello" if not formal else "Greetings"
        typer.echo(f"{prefix} {name} " * count)

    runner = CliRunner()
    result = runner.invoke(app, ["Ada", "--count", "2", "--formal"])
    assert result.exit_code == 0
    assert result.output.strip() == "Greetings Ada Greetings Ada"
