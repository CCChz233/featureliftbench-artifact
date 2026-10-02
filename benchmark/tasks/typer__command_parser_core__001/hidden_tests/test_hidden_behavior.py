from __future__ import annotations

from typing import Literal, Optional

import featurelifted as typer
from featurelifted.testing import CliRunner


def test_subcommands_and_optional_path() -> None:
    app = typer.Typer()
    users = typer.Typer()
    app.add_typer(users, name="users")

    @users.command()
    def create(name: str, email: Optional[str] = None):
        typer.echo(f"create:{name}:{email or ''}")

    runner = CliRunner()
    ok = runner.invoke(app, ["users", "create", "Ada", "--email", "a@example.com"])
    assert ok.exit_code == 0
    assert ok.output.strip() == "create:Ada:a@example.com"

    bad = runner.invoke(app, ["users", "create"])
    assert bad.exit_code != 0


def test_choice_validation() -> None:
    app = typer.Typer()

    @app.command()
    def mode(value: Literal["fast", "slow"] = "fast"):
        typer.echo(value)

    runner = CliRunner()
    bad = runner.invoke(app, ["--value", "turbo"])
    assert bad.exit_code != 0
