""" A Click command for documenting database objects to Confluence. """

import asyncio
import json
import os
import pathlib
import tempfile
import time
import click

from palje.confluence.confluence_ops import (
    is_page_creation_allowed_async,
    sort_child_pages_alphabetically_async,
)
from palje.confluence.confluence_rest import ConfluenceRestClientAsync
from palje.confluence.utils import (
    show_db_data_collecting_progress,
    show_page_creation_progress,
    show_page_sorting_progress,
)
from palje.db_to_confluence import (
    ConfluencePageMapEntry,
    create_confluence_db_doc_files,
    create_confluence_pages_from_entries_recursively_async,
)
from palje.mssql.mssql_database import MSSQLDatabaseAuthType, MSSQLDatabase
from palje.progress_tracker import ProgressTracker

# TODO: Fix issue with [default: (dynamic)] in help text


# TODO: Move to utils or similar
def _page_map_dict_to_entries(d: dict) -> ConfluencePageMapEntry:
    """Recursively convert a page map dict to ConfluencePageMapEntry hierarchy"""
    entry = ConfluencePageMapEntry(
        page_title=d["page_title"],
        page_content_file=pathlib.Path(d["page_content_file"]),
    )
    entry.child_pages = [_page_map_dict_to_entries(child) for child in d["child_pages"]]
    return entry


@click.command(
    help="Create or update database documentation in Confluence. Notice that"
    + " Confluence page titles are unique per space, and any existing page gets updated"
    + " wherever it happens to be located. This counts for the parent page as well"
    + " all child pages.",
    name="document",
)
@click.option(
    "--target-confluence-root-url",
    help="Confluence root URL. Optionally read from env var "
    + "PALJE_TARGET_CONFLUENCE_ROOT_URL. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_TARGET_CONFLUENCE_ROOT_URL", ""),
)
@click.option(
    "--target-confluence-space-key",
    help="Key of the target Confluence space. "
    + "Optionally read from env var PALJE_TARGET_CONFLUENCE_SPACE_KEY. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_TARGET_CONFLUENCE_SPACE_KEY", ""),
)
@click.option(
    "--target-atlassian-user-id",
    help="Atlassian user id for accessing Confluence. Typically an email address. "
    + "Optionally read from env var PALJE_TARGET_ATLASSIAN_USER_ID. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_TARGET_ATLASSIAN_USER_ID", ""),
)
@click.option(
    "--target-atlassian-api-token",
    help="Atlassian API token for accessing Confluence. Optionally read from env var "
    + "PALJE_ATLASSIAN_API_TOKEN. Prompted for if not available at runtime.",
    show_default=False,
    default=lambda: os.environ.get("PALJE_TARGET_ATLASSIAN_API_TOKEN", ""),
)
@click.option(
    "--db-auth",
    type=click.Choice(["SQL", "Windows", "AAD", "AzureIdentity"]),
    help="Database authentication method. Optionally read from env var "
    + "PALJE_DB_AUTH.",
    default=lambda: os.environ.get("PALJE_DB_AUTH", "SQL"),
    callback=lambda _ctx, _param, value: MSSQLDatabaseAuthType[value],
    show_default=True,
)
@click.option(
    "--db-driver",
    type=click.Choice(MSSQLDatabase.available_db_drivers()),
    default=lambda: os.environ.get(
        "PALJE_DB_DRIVER", MSSQLDatabase.available_db_drivers()[0]
    ),
    show_default=True,
    help="Name of the pyodbc driver to use for database connection. Optionally read "
    + "from env var PALJE_DB_DRIVER.",
)
@click.option(
    "--db-server",
    help="Host name of the SQL Server. If needed, include the port number separated "
    + "with a comma e.g. 'localhost,14430'. Optionally read from env var "
    + "PALJE_DB_SERVER."
    + " Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_DB_SERVER", ""),
)
@click.option(
    "--db-name",
    help="Name of the database to document. Optionally read from env var PALJE_DB_NAME."
    + " Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_DB_NAME", ""),
)
@click.option(
    "--db-username",
    help="Login username for the SQL Server, if needed by the auth type. Optionally"
    + " read from env var PALJE_DB_USERNAME."
    + " Prompted for if required and not available at runtime.",
    default=lambda: os.environ.get("PALJE_DB_USERNAME", ""),
)
@click.option(
    "--db-password",
    help="Login password for the SQL Server, if needed by the auth type. Optionally "
    + "read from env var PALJE_DB_PASSWORD."
    + " Prompted for if required and not available at runtime.",
    default=lambda: os.environ.get("PALJE_DB_PASSWORD", ""),
)
@click.option(
    "--parent-page-title",
    help="Title of the Confluence page under which the documentation is created. "
    + "If not given, a default name will be derived from the database name. "
    + 'Enter the value in "double quotes" if it contains whitespace.',
)
@click.option(
    "--schema",
    "-s",
    multiple=True,
    help="Name(s) of the schema(s) to document. If not given, all schemas will be "
    + "documented. Use multiple times to specify multiple schemas.",
)
@click.option(
    "--dependency-db",
    "-d",
    multiple=True,
    help="Name(s) of the database(s) where object dependencies are sought. "
    + "If not given, dependencies are sought only in the documented database. "
    + "Use multiple times to specify multiple databases.",
)
@click.option(
    "--work-dir",
    help="Optional path to a directory where the work files will be stored. "
    + "Given directory is not removed after the operation. "
    + "If not given, uses a system provided temporary directory.",
    required=False,
    type=click.Path(exists=True, file_okay=False, writable=True),
)
def document_db_to_confluence(
    target_confluence_root_url: str,
    target_confluence_space_key: str,
    target_atlassian_user_id: str,
    target_atlassian_api_token: str,
    db_auth: MSSQLDatabaseAuthType,
    db_driver: str,
    db_server: str,
    db_name: str,
    db_username: str,
    db_password: str,
    parent_page_title: str,
    schema: tuple[str, ...],
    dependency_db: tuple[str, ...],
    work_dir: pathlib.Path | None,
) -> int:
    """Document database objects to Confluence.

    Arguments
    ---------
    target_confluence_root_url : str
        The root URL of the Confluence server.

    target_confluence_space_key : str
        The key of the Confluence space.

    target_atlassian_user_id : str
        The Atlassian user id.

    target_atlassian_api_token : str
        The Atlassian API token.

    db_auth : MSSQLDatabaseAuthType
        The authentication method to the database.

    db_driver : str
        The name of the database driver.

    db_server : str
        Database server address.
        May contain comma-separated port e.g. 'localhost,14430'.

    db_name : str
        The name of the database to document.

    db_username : str
        The username for reading the database. Not relevant to all auth types.

    db_password : str
        The password for the db_username. Not relevant to all auth types.

    parent_page_title : str
        The title of an existing parent page in Confluence. If not given, a the
        documentation is placed in the space root under a page with title derived from
        the database name. Content of the parent page will be overwritten with a
        table of contents to the underlying documention.

    schema : tuple[str, ...]
        The schemas to document.

    dependency_db : tuple[str, ...]
        The databases where object dependencies are sought.

    use_concurrency : bool
        Use concurrency to improve performance. Notice: page order will be random!

    max_concurrency : int
        The maximum concurrency of the operation.

    Returns
    -------
    int
        The return value of the operation. Zero on success.

    """
    # Prompt for missing params

    if not target_confluence_root_url:
        target_confluence_root_url = click.prompt("Confluence root URL")

    if not target_confluence_space_key:
        target_confluence_space_key = click.prompt("Confluence space key")

    if not target_atlassian_user_id:
        target_atlassian_user_id = click.prompt("Atlassian user ID")

    if not target_atlassian_api_token:
        target_atlassian_api_token = click.prompt(
            "Atlassian API token", hide_input=True
        )

    if not db_server:
        db_server = click.prompt("Database server")

    if not db_name:
        db_name = click.prompt("Database")

    if db_auth not in [
        MSSQLDatabaseAuthType.WINDOWS,
        MSSQLDatabaseAuthType.AAD,
        MSSQLDatabaseAuthType.AZURE_IDENTITY,
    ]:
        if not db_username:
            db_username = click.prompt("Database username")
        if not db_password:
            db_password = click.prompt("Database password", hide_input=True)

    # Setup db connection

    click.echo(f"Connecting to database {db_name}@{db_server}...")
    click.echo(f"  pyodbc driver: {db_driver}")
    click.echo(f"  authentication: {db_auth.value}")

    try:
        # TODO: move auth logic / parameter handling into MSSQLDatabase
        if db_auth == MSSQLDatabaseAuthType.WINDOWS:
            database_client = MSSQLDatabase(
                server=db_server,
                database=db_name,
                driver=db_driver,
                authentication=db_auth,
            )
        else:
            database_client = MSSQLDatabase(
                server=db_server,
                database=db_name,
                driver=db_driver,
                authentication=db_auth,
                username=db_username,
                password=db_password,
            )

        database_client.connect()
    except Exception as e:
        click.secho(f"Connecting to database failed. {e}", fg="red")
        return 1
    click.echo(f"Connected to database {db_name}@{db_server}")

    available_databases = database_client.get_databases()
    if database_client.database not in available_databases:
        # This happens if the database name has different case
        # than in sys.databases.
        suggested_db = [
            db
            for db in available_databases
            if db.lower() == database_client.database.lower()
        ][0]
        raise click.UsageError(
            f"Database '{database_client.database}' was not found on the server. "
            + f"Did you mean '{suggested_db}'?"
        )

    data_collect_pt = ProgressTracker(on_step_callback=show_db_data_collecting_progress)
    # FIXME: get rid of unclear default 1's
    confl_update_pt = ProgressTracker(
        on_step_callback=show_page_creation_progress, target_total=1
    )
    confl_sort_pt = ProgressTracker(
        on_step_callback=show_page_sorting_progress, target_total=1
    )

    start = time.perf_counter()
    ret_val = 0
    try:
        asyncio.run(
            _document_db_to_confluence_async(
                target_confluence_root_url,
                target_atlassian_user_id,
                target_atlassian_api_token,
                database_client,
                target_confluence_space_key,
                parent_page_title,
                list(set(schema)),
                list(set(dependency_db)),
                confl_update_pt=confl_update_pt,
                doc_files_pt=data_collect_pt,
                confl_sort_pt=confl_sort_pt,
                work_dir=work_dir,
            )
        )
        click.echo()
        end = time.perf_counter()
        elapsed_time = end - start
        click.echo(
            (
                f"Database documentation completed in {elapsed_time:.03f} seconds."
                + f" Total pages affected: {confl_update_pt.completed}."
                + (
                    f" ({confl_update_pt.failed} failures)"
                    if confl_update_pt.failed
                    else ""
                )
            )
        )
    except Exception as e:
        click.secho(f"\nOperation failed. {e}", fg="red")
        ret_val = 1
    finally:
        database_client.close()

    return ret_val


async def _document_db_to_confluence_async(
    tgt_confluence_root_url: str,
    tgt_atlassian_user_id: str,
    tgt_atlassian_api_token: str,
    database_client: MSSQLDatabase,
    tgt_confluence_space_key: str,
    parent_page_title: str,
    schema: tuple[str, ...],
    dependency_db: tuple[str, ...],
    doc_files_pt: ProgressTracker,
    confl_update_pt: ProgressTracker,
    confl_sort_pt: ProgressTracker,
    work_dir: pathlib.Path | None = None,
):

    if not work_dir:
        tmp_work_dir = tempfile.TemporaryDirectory()
        work_dir_root = pathlib.Path(tmp_work_dir.name)
        click.echo(f"Using temporary work dir: {work_dir_root.absolute()}")
    else:
        work_dir_root = pathlib.Path(work_dir)

    async with ConfluenceRestClientAsync(
        tgt_confluence_root_url,
        tgt_atlassian_user_id,
        tgt_atlassian_api_token,
        progress_callback=doc_files_pt.step,
    ) as confluence_client:

        click.echo(f"Checking Confluence permissions for page creation ... ", nl=False)
        is_writable_space = await is_page_creation_allowed_async(
            confluence_client=confluence_client, space_key=tgt_confluence_space_key
        )
        click.echo("OK" if is_writable_space else "FAILED")
        if not is_writable_space:
            raise click.ClickException(
                f"Space key#{tgt_confluence_space_key} doesn't allow page creation."
            )

        confluence_space_id = await confluence_client.get_space_id_async(
            space_key=tgt_confluence_space_key
        )

        if parent_page_title:
            parent_page_id = await confluence_client.get_page_id_async(
                space_id=confluence_space_id, page_title=parent_page_title
            )
            if not parent_page_id:
                raise click.ClickException(
                    f"Parent page '{parent_page_title}' not found in space '{tgt_confluence_space_key}'."
                )
        else:
            parent_page_id = None

        page_map_file = await create_confluence_db_doc_files(
            db_client=database_client,
            output_dir=work_dir_root,
            parent_page_title=parent_page_title,
            schemas=schema,
            additional_databases=dependency_db,
            progress_tracker=doc_files_pt,
        )

    click.echo()
    async with ConfluenceRestClientAsync(
        tgt_confluence_root_url,
        tgt_atlassian_user_id,
        tgt_atlassian_api_token,
        progress_callback=confl_update_pt.step,
    ) as confluence_client:

        # Read page map file
        with open(page_map_file, "r") as f:
            page_map_dict = json.loads(f.read())

        page_map_root_entry = _page_map_dict_to_entries(page_map_dict)

        root_page_id = await create_confluence_pages_from_entries_recursively_async(
            confluence_client=confluence_client,
            confluence_space_id=confluence_space_id,
            parent_page_id=parent_page_id,
            page_map_root_entry=page_map_root_entry,
            progress_tracker=confl_update_pt,
        )

    click.echo()
    async with ConfluenceRestClientAsync(
        tgt_confluence_root_url,
        tgt_atlassian_user_id,
        tgt_atlassian_api_token,
        progress_callback=confl_sort_pt.step,
    ) as confluence_client:

        await sort_child_pages_alphabetically_async(
            confluence_client=confluence_client,
            page_id=root_page_id,
            recursive=True,
            case_sensitive=False,
            progress_tracker=confl_sort_pt,
        )
