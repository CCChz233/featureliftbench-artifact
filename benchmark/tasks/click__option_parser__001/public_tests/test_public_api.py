from __future__ import annotations

import featurelifted as click
from featurelifted.testing import CliRunner


def test_command_options_arguments_and_choice_errors() -> None:
    @click.command()
    @click.option("--count", default=1, type=int)
    @click.option("--mode", type=click.Choice(["fast", "slow"]), default="fast")
    @click.argument("name")
    def cli(count, mode, name):
        click.echo(f"{name}:{mode}:{count}")

    runner = CliRunner()
    result = runner.invoke(cli, ["--count", "3", "--mode", "slow", "Ada"])
    assert result.exit_code == 0
    assert result.output.strip() == "Ada:slow:3"

    bad = runner.invoke(cli, ["--mode", "bad", "Ada"])
    assert bad.exit_code == 2
    assert "Invalid value for '--mode'" in bad.output
