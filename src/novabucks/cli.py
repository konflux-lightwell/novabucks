import click

from novabucks import __version__


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="novabucks")
@click.pass_context
def main(ctx):
    """CLI tool for signing Maven artifacts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(2)


@main.command()
def sign():
    """Sign Maven artifacts."""
    click.echo("sign: not yet implemented", err=True)
    raise SystemExit(1)
