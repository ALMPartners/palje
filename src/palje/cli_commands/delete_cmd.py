""" A Click command for deleting Confluence page(s). """

import asyncio
import os
from typing import Any
import click

# TODO: prefix https://click.palletsprojects.com/en/8.1.x/options/#values-from-environment-variables

from palje.confluence.confluence_ops import (
    delete_confluence_pages_async,
    get_confluence_page_by_id_async,
    get_confluence_page_by_title_async,
    get_confluence_page_hierarchy_async,
    is_page_deletion_allowed_async,
)
from palje.confluence.confluence_rest import (
    ConfluenceRESTNotFoundError,
    ConfluenceRestClientAsync,
)
from palje.progress_tracker import ProgressTracker


def _display_page_find_progress(pt: ProgressTracker) -> None:
    """Print current page finding progress to the console."""
    click.echo(
        f"\rChild pages found: {pt.target_total} ... {pt.elapsed_time:.2f}s",
        nl=False,
    )


def _display_page_deletion_progress(pt: ProgressTracker) -> None:
    """Print current page deletion progress to the console."""
    click.echo(
        f"\rPages deleted: {pt.passed} / {pt.target_total}"
        + f" ... {pt.elapsed_time:.2f}s ... {pt.message: <150}",
        nl=False,
    )


def _check_page_identification_params(
    ctx: click.Context, param: click.Option, value: Any
) -> Any:
    """Check that page identification parameters are used correctly."""
    if param.name == "page_id":
        ctx.params["page_id"] = value
    if param.name == "page_title":
        if ctx.params.get("page_id", None) is not None:
            if value:
                raise click.BadOptionUsage(
                    param.name, "Only either --page-id OR --page-title may be provided "
                )
    return value


@click.command(help="Delete page(s) from Confluence.", name="delete")
@click.option(
    "--confluence-root-url",
    help="Confluence root URL. Optionally read from env var "
    + "PALJE_CONFLUENCE_ROOT_URL. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_ROOT_URL", ""),
)
@click.option(
    "--atlassian-user-id",
    help="Atlassian user id for accessing Confluence. Typically an email address. "
    + "Optionally read from env var PALJE_ATLASSIAN_USER_ID. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_ATLASSIAN_USER_ID", ""),
)
@click.option(
    "--atlassian-api-token",
    help="Atlassian API token for accessing Confluence. Optionally read from env var "
    + "PALJE_ATLASSIAN_API_TOKEN. Prompted for if not available at runtime.",
    hide_input=True,
    show_default=False,
    default=lambda: os.environ.get("PALJE_ATLASSIAN_API_TOKEN", ""),
)
@click.option(
    "--keep-children",
    help="Keep child pages. By default, children are deleted with the parent.",
    is_flag=True,
)
@click.option(
    "--page-id",
    help="Id of the page to delete. May be used instead of --page-title and "
    + "--confluence-space-key.",
    callback=_check_page_identification_params,
    is_eager=True,  # makes sure --page-id seen before other page identifying params
)
@click.option(
    "--page-title",
    help="Title of the page to delete (instead of --page-id). "
    + "Requires Confluence space key to be available, too.",
    callback=_check_page_identification_params,
)
@click.option(
    "--confluence-space-key",
    help="Space key of the Confluence page to delete by its --page-title. "
    + "Optionally read from env var "
    + "PALJE_CONFLUENCE_SPACE_KEY. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_SPACE_KEY", ""),
)
@click.pass_context
def delete_confluence_page(
    ctx: click.Context,
    page_id,
    confluence_root_url: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    keep_children: bool,
    page_title: str,
    confluence_space_key: str,
) -> int:
    """Delete a Confluence page, optionally and by default with its children.
    Deletion can be done either by page id OR by page title and space key.

    Arguments
    ---------

    ctx : click.Context
        Click context. Used for passing global options.

    page_id : int
        The page id to delete. Not to be used with --page-title and
        --confluence-space-key.

    confluence_root_url : str
        The root URL of the Confluence server.

    atlassian_user_id : str
        The Atlassian user id of the user.

    atlassian_api_token : str
        Atlassian API token of the user.

    keep_children : bool
        Whether to keep the children of the page. Default is False.

    page_title : str
        Title of the page to delete (instead of page id). Space key must be
        provided separately.

    confluence_space_key : str
        Space key of the page to delete. Page title must be provided separately

    Returns
    -------

    int
        Zero if successful.

    """

    page_find_pt = ProgressTracker(on_step_callback=_display_page_find_progress)
    page_delete_pt = ProgressTracker(on_step_callback=_display_page_deletion_progress)

    try:
        if not page_id and not (page_title):
            raise click.UsageError("Either --page-id OR --page-title must be provided.")

        if not confluence_root_url:
            confluence_root_url = click.prompt("Confluence root URL")

        if not atlassian_user_id:
            atlassian_user_id = click.prompt("Atlassian user ID")

        if not atlassian_api_token:
            atlassian_api_token = click.prompt("Atlassian API token", hide_input=True)

        if not page_id:
            if not confluence_space_key:
                confluence_space_key = click.prompt("Confluence space key")

        asyncio.run(
            _delete_confluence_page_async(
                confluence_root_url=confluence_root_url,
                atlassian_user_id=atlassian_user_id,
                atlassian_api_token=atlassian_api_token,
                page_id=page_id,
                page_title=page_title,
                confluence_space_key=confluence_space_key,
                keep_children=keep_children,
                yes_to_all=(ctx and ctx.obj["yes_to_all"]),
                page_find_pt=page_find_pt,
                page_delete_pt=page_delete_pt,
            )
        )

        click.echo(
            (
                "\nPage deletion completed."
                + f" Total pages affected: {page_delete_pt.completed}."
                + (
                    f" ({page_delete_pt.failed} failures)"
                    if page_delete_pt.failed
                    else ""
                )
            )
        )
        return 0

    except Exception as e:
        click.secho(f"\nPage deletion aborted. {e}", fg="red")
        return 1


async def _delete_confluence_page_async(
    confluence_root_url: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    page_id: int | None = None,
    page_title: str | None = None,
    confluence_space_key: str | None = None,
    keep_children: bool = True,
    yes_to_all: bool = False,
    page_find_pt: ProgressTracker | None = None,
    page_delete_pt: ProgressTracker | None = None,
) -> int:
    async with ConfluenceRestClientAsync(
        root_url=confluence_root_url,
        user_id=atlassian_user_id,
        api_token=atlassian_api_token,
    ) as confluence_client:
        try:
            if page_id:
                page_to_delete = await get_confluence_page_by_id_async(
                    confluence_client=confluence_client,
                    page_id=page_id,
                )
            else:
                page_to_delete = await get_confluence_page_by_title_async(
                    confluence_client=confluence_client,
                    page_title=page_title,
                    space_key=confluence_space_key,
                )
        except ConfluenceRESTNotFoundError as e:
            page_identifier = f"{page_id}" if page_id else f"'{page_title}'"
            space_identifier = (
                f" from space '{confluence_space_key}'"
                if confluence_space_key and not page_id
                else ""
            )
            message = f"Couldn't find page {page_identifier}" + f"{space_identifier}."
            raise ValueError(message) from e

        click.echo(
            f"Preparing deletion of page {page_to_delete}"
            + (
                f" in space {confluence_space_key}"
                # when deleting directly by id, the space key is omitted
                if confluence_space_key and page_title
                else ""
            )
            + (" with all its children" if not keep_children else "")
            + " ..."
        )

        click.echo(f"Checking Confluence permissions for page deletion ... ", nl=False)
        page_deletion_allowed = await is_page_deletion_allowed_async(
            confluence_client=confluence_client,
            page_id=page_to_delete.id,
        )
        click.echo("OK" if page_deletion_allowed else "FAILED")
        if not page_deletion_allowed:
            raise click.ClickException(
                f"Deletion of page {page_to_delete} is not allowed."
            )

        pages_to_delete = [page_to_delete]

        if keep_children:
            page_list_str = f"  {page_to_delete}"
        else:
            click.echo("Finding child pages ...")
            page_hierarchy = await get_confluence_page_hierarchy_async(
                confluence_client=confluence_client,
                page_id=page_to_delete.id,
                progress_tracker=page_find_pt,
            )
            pages_to_delete = page_hierarchy.pages
            page_list_str = page_hierarchy.tree_str(indent=2)

        if not yes_to_all:
            click.echo("\nPage(s) to be deleted:\n")
            click.echo(page_list_str)
            click.secho(
                f"WARNING: About to delete {len(pages_to_delete)} page(s).",
                fg="yellow",
            )
            click.confirm("Do you want to proceed?", abort=True)

        await delete_confluence_pages_async(
            confluence_client=confluence_client,
            pages=pages_to_delete,
            progress_tracker=page_delete_pt,
        )
