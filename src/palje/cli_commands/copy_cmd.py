import asyncio
import os
import pathlib
import tempfile

import click

from palje.confluence.confluence_ops import (
    copy_confluence_pages_async,
    get_confluence_page_by_id_async,
    get_confluence_page_by_title_async,
    get_confluence_page_hierarchy_async,
    check_for_duplicate_page_titles_async,
    is_page_creation_allowed_async,
    reorder_page_hierarchy_async,
)
from palje.confluence.confluence_rest import (
    ConfluenceRESTError,
    ConfluenceRestClientAsync,
)
from palje.confluence.utils import (
    show_page_finding_progress,
    show_page_sorting_progress,
)
from palje.progress_tracker import ProgressTracker


def _display_page_copying_progress(pt: ProgressTracker) -> None:
    """Print current page copying progress to the console."""
    click.echo(
        f"\rPages copied: {pt.passed}/{pt.target_total} ... {pt.elapsed_time:.2f}s"
        + f" ... {pt.message : <150}",
        nl=False,
    )


def _check_page_identification_params(ctx, param, value):
    """Check that page identification parameters are provided correctly."""
    if param.name == "page_id":
        ctx.params["page_id"] = value
    if param.name == "page_title":
        if ctx.params.get("page_id", None) is not None:
            if value:
                raise click.BadOptionUsage(
                    param.name, "Only either --page-id OR --page-title may be provided "
                )
    return value


@click.command(
    help="Experimental: Copy pages or page hierarchies between Confluence instances "
    + "and spaces.",
    name="copy",
)
#
# region Source page identification
#
@click.option(
    "--confluence-root-url",
    help="Source Confluence root URL. Optionally read from env var "
    + "PALJE_CONFLUENCE_ROOT_URL. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_ROOT_URL", ""),
)
@click.option(
    "--confluence-space-key",
    help="Space key of the Confluence page to copy by its --page-title. "
    + "Optionally read from env var PALJE_CONFLUENCE_SPACE_KEY. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_SPACE_KEY", ""),
)
@click.option(
    "--atlassian-user-id",
    help="Atlassian user id for accessing the source Confluence. Typically an email address. "
    + "Optionally read from env var PALJE_ATLASSIAN_USER_ID. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_ATLASSIAN_USER_ID", ""),
)
@click.option(
    "--atlassian-api-token",
    help="Atlassian API token for accessing the source Confluence. Optionally read from env var "
    + "PALJE_ATLASSIAN_API_TOKEN. Prompted for if not available at runtime.",
    hide_input=True,
    show_default=False,
    default=lambda: os.environ.get("PALJE_ATLASSIAN_API_TOKEN", ""),
)
# TODO: page id and title could be repeatable? (for copying multiple pages)
@click.option(
    "--page-id",
    help="Id of the page to copy. May be used instead of --page-title and "
    + "--confluence-space-key.",
    callback=_check_page_identification_params,
    is_eager=True,  # makes sure --page-id seen before other page identifying params
)
@click.option(
    "--page-title",
    help="Title of the page to copy (instead of --page-id). "
    + "Requires --confluence-space-key to be available, too.",
    callback=_check_page_identification_params,
)
#
# endregion Source page identification
# region Target Confluence details
#
# TODO: same Confluence instance, different space -> optionally use the same credentials
#       --local?
@click.option(
    "--target-confluence-root-url",
    help="Confluence root URL. Optionally read from env var "
    + "PALJE_TARGET_CONFLUENCE_ROOT_URL. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_TARGET_CONFLUENCE_ROOT_URL", ""),
)
@click.option(
    "--target-confluence-space-key",
    help="Space key of the Confluence page to copy by its --page-title. "
    + "Optionally read from env var "
    + "PALJE_TARGET_CONFLUENCE_SPACE_KEY. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_TARGET_CONFLUENCE_SPACE_KEY", ""),
)
@click.option(
    "--target-atlassian-user-id",
    help="Atlassian user id for accessing target Confluence. Typically an email address. "
    + "Optionally read from env var PALJE_TARGET_ATLASSIAN_USER_ID. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_TARGET_ATLASSIAN_USER_ID", ""),
)
@click.option(
    "--target-atlassian-api-token",
    help="Atlassian API token for accessing target Confluence. Optionally read from env var "
    + "PALJE_TARGET_ATLASSIAN_API_TOKEN. Prompted for if not available at runtime.",
    hide_input=True,
    show_default=False,
    default=lambda: os.environ.get("PALJE_TARGET_ATLASSIAN_API_TOKEN", ""),
)
# TODO: opt switch: use the same credentials for source and target unless specified
# endregion Target Confluence details
@click.option(
    "--no-children",
    help="Copy the given page and all child pages it may have.",
    is_flag=True,
)
@click.option(
    "--page-title-prefix",
    help="Leading string to add to the originial page title when creating a copy. "
    + "Applied to all copied pages exactly as given, so include any "
    + "separating whitespace into the value if you need it.",
    required=False,
)
@click.option(
    "--page-title-postfix",
    help="Trailing string to add to the originial page title when creating a copy. "
    + "Applied to all copied pages exactly as given, so include any "
    + "separating whitespace into the value if you need it.",
    required=False,
)
@click.option(
    "--work-dir",
    help="Optional path to a directory where the work files will be stored. "
    + "Given directory is not removed after the operation. "
    + "If not provided, a temporary directory is used.",
    required=False,
    type=click.Path(exists=True, file_okay=False, writable=True),
)
# TODO: parent page id or title (all pages go under the same parent?)


@click.pass_context
def copy_confluence_page(
    ctx: click.Context,
    confluence_root_url: str,
    confluence_space_key: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    page_id: int,
    page_title: str,
    target_confluence_root_url: str,
    target_confluence_space_key: str,
    target_atlassian_user_id: str,
    target_atlassian_api_token: str,
    no_children: bool,
    work_dir: click.Path,
    page_title_prefix: str,
    page_title_postfix: str,
) -> int:
    """Copy page(s) between Confluence instances or spaces.

    This is an EXPERIMENTAL feature!

    There are known ISSUES including but not limited to:

        - while the embedded image attachments are shown OK on the copied
          page, they break instantly when the page is edited in the web-UI
        - _very_ limited support for special / 3rd party attachments (gliffy only)
        - special characters in attachment filenames are not handled properly;
          e.g. image attachments with such names will appear broken on the copied page
    """

    copy_children = no_children == False

    if not page_id:
        if not confluence_space_key:
            confluence_space_key = click.prompt("Source Confluence space key")
        if not page_title:
            page_title = click.prompt("Source Confluence page title")

    # Source Confluence

    page_finding_pt = ProgressTracker(on_step_callback=show_page_finding_progress)
    page_sorting_pt = ProgressTracker(on_step_callback=show_page_sorting_progress)
    page_copying_pt = ProgressTracker(on_step_callback=_display_page_copying_progress)

    if not confluence_root_url:
        confluence_root_url = click.prompt("Source Confluence root URL")

    if not atlassian_user_id:
        atlassian_user_id = click.prompt("Atlassian user ID for source Confluence")

    if not atlassian_api_token:
        atlassian_api_token = click.prompt(
            "Atlassian API token for source Confluence", hide_input=True
        )

    # Target Confluence

    if not target_confluence_root_url:
        target_confluence_root_url = click.prompt("Target Confluence root URL")

    if not target_atlassian_user_id:
        target_atlassian_user_id = click.prompt(
            "Atlassian user ID for target Confluence"
        )

    if not target_atlassian_api_token:
        target_atlassian_api_token = click.prompt(
            "Atlassian API token for target Confluence", hide_input=True
        )

    if not target_confluence_space_key:
        target_confluence_space_key = click.prompt("Target Confluence space key")

    # Source and target space are the same -cases

    try:
        if confluence_root_url == target_confluence_root_url:
            if confluence_space_key == target_confluence_space_key:
                if not (page_title_prefix or page_title_postfix):
                    message = (
                        "Due to Confluence page titles having to be unique within a space, "
                        + "either --page-title-prefix or --page-title-postfix MUST be "
                        + "given when copying pages within the same space."
                    )
                    raise click.ClickException(message)

        asyncio.run(
            _copy_confluence_page_async(
                confluence_root_url=confluence_root_url,
                atlassian_user_id=atlassian_user_id,
                atlassian_api_token=atlassian_api_token,
                confluence_space_key=confluence_space_key,
                target_confluence_root_url=target_confluence_root_url,
                target_atlassian_user_id=target_atlassian_user_id,
                target_atlassian_api_token=target_atlassian_api_token,
                target_confluence_space_key=target_confluence_space_key,
                page_id=page_id,
                page_title=page_title,
                work_dir=work_dir,
                copy_children=copy_children,
                page_title_prefix=page_title_prefix,
                page_title_postfix=page_title_postfix,
                yes_to_all=(ctx and ctx.obj.get("yes_to_all", False)),
                page_finding_pt=page_finding_pt,
                page_sorting_pt=page_sorting_pt,
                page_copying_pt=page_copying_pt,
            )
        )
        click.echo("\nPage copying completed.")
    except Exception as e:
        click.secho(f"Operation failed. Error: {e}", fg="red")
        return -1

    return 0


async def _copy_confluence_page_async(
    confluence_root_url,
    atlassian_user_id,
    atlassian_api_token,
    target_confluence_root_url,
    target_atlassian_user_id,
    target_atlassian_api_token,
    page_id: int,
    page_title: str,
    confluence_space_key: str,
    target_confluence_space_key: str,
    work_dir: pathlib.Path,
    copy_children: bool,
    page_title_prefix: str,
    page_title_postfix: str,
    yes_to_all: bool = False,
    page_finding_pt: ProgressTracker | None = None,
    page_sorting_pt: ProgressTracker | None = None,
    page_copying_pt: ProgressTracker | None = None,
) -> None:
    """Copy a Confluence page and optionally its children."""

    src_confluence: ConfluenceRestClientAsync | None = None
    tgt_confluence: ConfluenceRestClientAsync | None = None
    tmp_work_dir: tempfile.TemporaryDirectory | None = None

    try:
        src_confluence = ConfluenceRestClientAsync(
            root_url=confluence_root_url,
            user_id=atlassian_user_id,
            api_token=atlassian_api_token,
        )

        tgt_confluence = ConfluenceRestClientAsync(
            root_url=target_confluence_root_url,
            user_id=target_atlassian_user_id,
            api_token=target_atlassian_api_token,
        )

        try:
            click.echo(
                f"Checking Confluence permissions for page creation ... ", nl=False
            )
            is_writable_space = await is_page_creation_allowed_async(
                confluence_client=tgt_confluence, space_key=target_confluence_space_key
            )
        except ConfluenceRESTError as err:
            click.echo("FAILED")
            raise click.ClickException(
                f"Failed to check page creation permissions for space "
                + f"'{target_confluence_space_key}'."
            ) from err
        click.echo("OK" if is_writable_space else "FAILED")
        if not is_writable_space:
            raise click.ClickException(
                f"Space '{target_confluence_space_key}' doesn't allow page creation."
            )

        try:
            page_to_copy = None
            if page_id:
                page_to_copy = await get_confluence_page_by_id_async(
                    confluence_client=src_confluence,
                    page_id=page_id,
                )
            elif page_title and confluence_space_key:
                page_to_copy = await get_confluence_page_by_title_async(
                    confluence_client=src_confluence,
                    space_key=confluence_space_key,
                    page_title=page_title,
                )
            else:
                raise click.ClickException(
                    "Either --page-id or --page-title AND --confluence-space-key "
                    + "must be provided."
                )
        except ConfluenceRESTError as err:
            page_identifier = f"id#{page_id}" if page_id else f"'{page_title}'"
            raise click.ClickException(
                f"Page {page_identifier} doesn't exist or is not available. {err}"
            ) from err

        # TODO: error handling

        source_page_titles: list[str] = []

        if copy_children:
            click.echo("Looking for child pages ...")
            orig_hierarchy = await get_confluence_page_hierarchy_async(
                confluence_client=src_confluence,
                page_id=page_to_copy.id,
                progress_tracker=page_finding_pt,
            )
            page_list_str = orig_hierarchy.tree_str(indent=2)
            click.echo(f"\n\n{page_list_str}")
            page_to_copy = orig_hierarchy.root_page
            page_copying_pt.target_total = len(orig_hierarchy.pages)
            source_page_titles = [p.title for p in orig_hierarchy.pages]
            click.echo(f"Found {len(source_page_titles)} pages to copy.")
        else:
            # TODO: included in the source_page_titles in the other case?
            source_page_titles.append(page_to_copy.title)
            page_copying_pt.target_total = 1
            click.echo(f"Found 1 page to copy.")

        click.echo("Checking existing pages in the target space ...")

        duplicates = await check_for_duplicate_page_titles_async(
            confluence_client=tgt_confluence,
            space_key=target_confluence_space_key,
            page_titles=source_page_titles,
            page_title_prefix=page_title_prefix,
            page_title_postfix=page_title_postfix,
        )
        num_duplicates = len(duplicates)
        if num_duplicates > 1:
            click.secho(
                f"WARNING: Copying will OVERWRITE {num_duplicates} existing pages!",
                fg="yellow",
            )
            click.secho(
                "Existing pages will be updated in-place i.e. if they exist outside of "
                + "the copied hierarchy, they will stay there.",
                fg="yellow",
            )
            click.secho(
                "If overwriting is not intended, and/or you want to ensure that all "
                + "copied pages end up in the same hierarchy, consider making the new "
                + "page titles unique with --page-title-prefix and/or "
                + "--page-title-postfix.",
                fg="yellow",
            )
        elif num_duplicates == 1:
            click.secho(
                "WARNING: Copying will OVERWRITE an existing page!",
                fg="yellow",
            )
            click.secho(
                "If overwriting is not intended, consider making the new "
                + "page title unique with --page-title-prefix and/or "
                + "--page-title-postfix.",
                fg="yellow",
            )
        else:
            click.echo("No conflicting page titles found. Nothing will be overwritten.")

        if not yes_to_all:
            click.confirm(
                f"Do you want to proceed and copy {len(source_page_titles)} pages?",
                abort=True,
            )

        if not work_dir:
            tmp_work_dir = tempfile.TemporaryDirectory()
            work_dir_root = pathlib.Path(tmp_work_dir.name)
            click.echo(f"Using temporary work dir: {work_dir_root.absolute()}")
        else:
            work_dir_root = pathlib.Path(work_dir)

        click.echo("Copying pages ...")

        new_page_id = await copy_confluence_pages_async(
            root_page=page_to_copy,
            src_confluence_client=src_confluence,
            confluence_space_key=confluence_space_key,
            tgt_confluence_client=tgt_confluence,
            target_confluence_space_key=target_confluence_space_key,
            work_dir=work_dir_root,
            copy_children=copy_children,
            page_title_prefix=page_title_prefix,
            page_title_postfix=page_title_postfix,
            progress_tracker=page_copying_pt,
        )

        click.echo("")

        # Async copying messes up the order of the copied pages -> reorder.
        click.echo("Reorganizing copied pages ...")

        await reorder_page_hierarchy_async(
            confluence_client=tgt_confluence,
            page_id=new_page_id,
            wanted_hierarchy_root=orig_hierarchy.root_page,
            page_title_prefix=page_title_prefix,
            page_title_postfix=page_title_postfix,
            recursive=copy_children,
            case_sensitive=False,
            progress_tracker=page_sorting_pt,
        )

    finally:
        # TODO: fix privates
        if tgt_confluence:
            await tgt_confluence._close()
        if src_confluence:
            await src_confluence._close()
        if tmp_work_dir:
            tmp_work_dir.cleanup()
