import asyncio
import os
from typing import Any
import click

from palje.confluence.confluence_ops import (
    sort_child_pages_alphabetically_async,
    get_confluence_page_by_id_async,
    get_confluence_page_by_title_async,
)
from palje.confluence.confluence_rest import ConfluenceRestClientAsync
from palje.confluence.utils import show_page_sorting_progress
from palje.progress_tracker import ProgressTracker


def _check_page_identification_params(
    ctx: click.Context, param: click.Option, value: Any
) -> Any:
    """Check that page identification parameters are used correctly."""
    if param.name == "parent_page_id":
        ctx.params["parent_page_id"] = value
    if param.name == "parent_page_title":
        if ctx.params.get("parent_page_id", None) is not None:
            if value:
                raise click.BadOptionUsage(
                    param.name,
                    "Only either --parent-page-id OR --parent-page-title may be "
                    + "provided.",
                )
    return value


@click.command(
    help="Sort child pages in alphabetical order by page title, optionally "
    + "recursively.",
    name="sort",
)
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
    "--confluence-space-key",
    help="Space key of the Confluence page hierarchy to sort. Required when "
    + "identifying the root page by title.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_SPACE_KEY", ""),
)
@click.option(
    "--parent-page-title",
    help="Title of the page whose child pages are to be sorted. Requires space "
    + "key, too.",
    callback=_check_page_identification_params,
)
@click.option(
    "--parent-page-id",
    help="Id of the page whose children are to be sorted.",
    callback=_check_page_identification_params,
    is_eager=True,  # makes sure id seen before other page identifying params
)
@click.option(
    "--recursive",
    help="Recursively sort all child page hierarchies, too. "
    + "By default, only the immediate child pages are sorted.",
    is_flag=True,
)
@click.option(
    "--case-sensitive",
    help="Sort with case-sensitive comparison. "
    + "By default, all titles are lower-cased for sorting.",
    default=False,
    is_flag=True,
)
@click.pass_context
def sort_confluence_page_hierarchy(
    ctx: click.Context,
    confluence_root_url: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    confluence_space_key: str | None = None,
    parent_page_title: str | None = None,
    parent_page_id: str | None = None,
    recursive: bool = False,
    case_sensitive: bool = False,
) -> int:
    page_sorting_pt = ProgressTracker(on_step_callback=show_page_sorting_progress)

    if not parent_page_id and not (parent_page_title):
        raise click.UsageError(
            "Either --parent-page-id OR --parent-page-title must be provided."
        )

    if not confluence_root_url:
        confluence_root_url = click.prompt("Confluence root URL")

    if not atlassian_user_id:
        atlassian_user_id = click.prompt("Atlassian user ID")

    if not atlassian_api_token:
        atlassian_api_token = click.prompt("Atlassian API token", hide_input=True)

    if not parent_page_id:
        if not confluence_space_key:
            confluence_space_key = click.prompt("Confluence space key")
    try:
        asyncio.run(
            _sort_child_pages_alphabetically_async(
                confluence_root_url=confluence_root_url,
                atlassian_user_id=atlassian_user_id,
                atlassian_api_token=atlassian_api_token,
                confluence_space_key=confluence_space_key,
                parent_page_title=parent_page_title,
                parent_page_id=parent_page_id,
                recursive=recursive,
                case_sensitive=case_sensitive,
                progress_tracker=page_sorting_pt,
            )
        )

        click.echo("\nPage sorting completed.")
    except Exception as err:
        click.secho(f"Operation failed. Error: {err}", fg="red")
        return 1

    return 0


async def _sort_child_pages_alphabetically_async(
    confluence_root_url: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    confluence_space_key: str | None = None,
    parent_page_title: str | None = None,
    parent_page_id: str | None = None,
    recursive: bool = False,
    case_sensitive: bool = False,
    progress_tracker: ProgressTracker | None = None,
) -> None:
    async with ConfluenceRestClientAsync(
        root_url=confluence_root_url,
        api_token=atlassian_api_token,
        user_id=atlassian_user_id,
    ) as confluence_client:
        if not parent_page_id:
            parent_page = await get_confluence_page_by_title_async(
                confluence_client=confluence_client,
                page_title=parent_page_title,
                space_key=confluence_space_key,
            )
        else:
            parent_page = await get_confluence_page_by_id_async(
                confluence_client=confluence_client,
                page_id=parent_page_id,
            )

        click.echo("Reorganizing pages ...")
        await sort_child_pages_alphabetically_async(
            confluence_client=confluence_client,
            page_id=parent_page.id,
            recursive=recursive,
            case_sensitive=case_sensitive,
            progress_tracker=progress_tracker,
        )
