from __future__ import annotations

import featurelifted as click
from featurelifted.testing import CliRunner


def test_group_context_flags_range_and_defaults() -> None:
    @click.group()
    @click.option("--debug/--no-debug", default=False)
    @click.pass_context
    def cli(ctx, debug):
        ctx.obj = {"debug": debug}

    @cli.command()
    @click.option("--level", type=click.IntRange(1, 5), default=2)
    @click.argument("name", required=False, default="world")
    @click.pass_context
    def greet(ctx, level, name):
        click.echo(f"{name}:{level}:{ctx.obj['debug']}")

    runner = CliRunner()
    ok = runner.invoke(cli, ["--debug", "greet", "--level", "4", "Ada"])
    assert ok.exit_code == 0
    assert ok.output.strip() == "Ada:4:True"

    defaulted = runner.invoke(cli, ["greet"])
    assert defaulted.exit_code == 0
    assert defaulted.output.strip() == "world:2:False"

    bad = runner.invoke(cli, ["greet", "--level", "9"])
    assert bad.exit_code == 2
    assert "9 is not in the range 1<=x<=5" in bad.output


def test_usage_errors_prompts_and_isolated_filesystem() -> None:
    @click.command()
    @click.option("--name", prompt=True)
    def cli(name):
        click.echo(f"hello {name}")

    runner = CliRunner()
    prompted = runner.invoke(cli, input="Ada\n")
    assert prompted.exit_code == 0
    assert "Name: Ada" in prompted.output
    assert "hello Ada" in prompted.output

    with runner.isolated_filesystem():
        with open("data.txt", "w", encoding="utf-8") as handle:
            handle.write("ok")

        @click.command()
        def read_file():
            with open("data.txt", encoding="utf-8") as handle:
                click.echo(handle.read())

        read_result = runner.invoke(read_file)
        assert read_result.exit_code == 0
        assert read_result.output.strip() == "ok"
