import os
import click

from palje.version import __version__ as PALJE_VERSION

from palje.cli_commands.copy_cmd import copy_confluence_page
from palje.cli_commands.sort_cmd import sort_confluence_page_hierarchy
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
    """
    palje provides a set of commands to interact with Confluence and MSSQL databases.

    With palje commands you can e.g. generate Confluence documentation from databases
    and manage content in Confluence.

    Use `palje2 COMMAND --help` to see more information on a specific command.
    """
    ctx.ensure_object(dict)
    ctx.obj["yes_to_all"] = yes_to_all


if os.getenv("PALJE_EXPERIMENTAL_FEATURES_ENABLED"):
    click.secho("Experimental features enabled.", fg="yellow")
    cli.add_command(copy_confluence_page, name="copy")

cli.add_command(document_db_to_confluence, name="document")
cli.add_command(delete_confluence_page, name="delete")
cli.add_command(document_db_to_confluence, name="document")
cli.add_command(sort_confluence_page_hierarchy, name="sort")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
