import click

from palje.version import __version__ as PALJE_VERSION

from palje.cli_commands.delete_cmd import delete_confluence_page
from palje.cli_commands.document_cmd import document_db_to_confluence


@click.group()
@click.version_option(PALJE_VERSION)
@click.option(
    "--yes-to-all",
    help="Skip all manual confirmations. Potentially dangerous!",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.pass_context
def cli(ctx: click.Context, yes_to_all: bool = False):
    ctx.ensure_object(dict)
    ctx.obj["yes_to_all"] = yes_to_all


cli.add_command(delete_confluence_page, name="delete")
cli.add_command(document_db_to_confluence, name="document")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
