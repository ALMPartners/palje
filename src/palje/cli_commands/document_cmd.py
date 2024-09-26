""" A Click command for documenting database objects to Confluence. """

import asyncio
import os
import click

from palje.confluence.confluence_ops import is_page_creation_allowed_async
from palje.confluence.confluence_rest import ConfluenceRestClientAsync
from palje.db_to_confluence import document_db_to_confluence_async
from palje.mssql.mssql_database import MSSQLDatabaseAuthType, MSSQLDatabase
from palje.progress_tracker import ProgressTracker


def _display_progress(pt: ProgressTracker):
    """Print current progress to the console."""
    click.echo(
        f"\rDocumenting database objects: {pt.passed} / {pt.target_total}"
        + f" ... {pt.elapsed_time:.2f}s ... {pt.message: <150}",
        nl=False,
    )


# TODO: Fix issue with [default: (dynamic)] in help text


@click.command(
    help="Create or update database documentation in Confluence. Notice that"
    + " Confluence page titles are unique per space, and any existing page gets updated"
    + " wherever it happens to be located. This counts for the parent page as well"
    + " all child pages.",
    name="document",
)

# TODO: move conf auth params to context (every palje command needs these?)
@click.option(
    "--confluence-root-url",
    help="Confluence root URL. Optionally read from env var "
    + "PALJE_CONFLUENCE_ROOT_URL. Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_ROOT_URL", ""),
)
@click.option(
    "--confluence-space-key",
    help="Key of the target Confluence space. "
    + "Optionally read from env var PALJE_CONFLUENCE_SPACE_KEY. "
    + "Prompted for if not available at runtime.",
    default=lambda: os.environ.get("PALJE_CONFLUENCE_SPACE_KEY", ""),
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
    show_default=False,
    default=lambda: os.environ.get("PALJE_ATLASSIAN_API_TOKEN", ""),
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
    + "If not given, a default name will be derived from the database name.",
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
    "--use-concurrency",
    default=False,
    is_flag=True,
    show_default=True,
    help="Improve performance by creating/updating multiple pages at the same time. "
    + "Unfortunately this effectively puts new pages in random order. Confluence REST "
    + "API doesn't support re-arranging of pages (CONFCLOUD-40101).",
)
@click.option(
    "--max-concurrency",
    default=2,
    show_default=True,
    help="Concurrency limit. Higher number may improve performance but can also lead "
    + "to unexpected failures. Only has effect with --use-concurrency.",
)
def document_db_to_confluence(
    confluence_root_url: str,
    confluence_space_key: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    db_auth: MSSQLDatabaseAuthType,
    db_driver: str,
    db_server: str,
    db_name: str,
    db_username: str,
    db_password: str,
    parent_page_title: str,
    schema: tuple[str, ...],
    dependency_db: tuple[str, ...],
    use_concurrency: bool,
    max_concurrency: int,
) -> int:
    """Document database objects to Confluence.

    Arguments
    ---------
    confluence_root_url : str
        The root URL of the Confluence server.

    confluence_space_key : str
        The key of the Confluence space.

    atlassian_user_id : str
        The Atlassian user id.

    atlassian_api_token : str
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
        The title of the parent page in Confluence. Empty value will be replaced
        with a default name derived from the database name.

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

    if not confluence_root_url:
        confluence_root_url = click.prompt("Confluence root URL")

    if not confluence_space_key:
        confluence_space_key = click.prompt("Confluence space key")

    if not atlassian_user_id:
        atlassian_user_id = click.prompt("Atlassian user ID")

    if not atlassian_api_token:
        atlassian_api_token = click.prompt("Atlassian API token", hide_input=True)

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

    progress_tracker = ProgressTracker(on_step_callback=_display_progress)

    ret_val = 0
    try:
        asyncio.run(
            _document_db_to_confluence_async(
                confluence_root_url,
                atlassian_user_id,
                atlassian_api_token,
                database_client,
                confluence_space_key,
                parent_page_title,
                list(set(schema)),
                list(set(dependency_db)),
                progress_tracker,
                use_concurrency,
                max_concurrency,
            )
        )
        click.echo()
        click.echo(
            (
                "Database documentation completed."
                + f" Total pages affected: {progress_tracker.completed}."
                + (
                    f" ({progress_tracker.failed} failures)"
                    if progress_tracker.failed
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
    confluence_root_url: str,
    atlassian_user_id: str,
    atlassian_api_token: str,
    database_client: MSSQLDatabase,
    confluence_space_key: str,
    parent_page_title: str,
    schema: tuple[str, ...],
    dependency_db: tuple[str, ...],
    progress_tracker: ProgressTracker,
    use_concurrency: bool,
    max_concurrency: int,
):
    async with ConfluenceRestClientAsync(
        confluence_root_url,
        atlassian_user_id,
        atlassian_api_token,
        progress_callback=progress_tracker.step,
    ) as confluence_client:
        click.echo(f"Checking Confluence permissions for page creation ... ", nl=False)
        is_writable_space = await is_page_creation_allowed_async(
            confluence_client=confluence_client, space_key=confluence_space_key
        )
        click.echo("OK" if is_writable_space else "FAILED")
        if not is_writable_space:
            raise click.ClickException(
                f"Space key#{confluence_space_key} doesn't allow page creation."
            )

        await document_db_to_confluence_async(
            confluence_client=confluence_client,
            db_client=database_client,
            confluence_space_key=confluence_space_key,
            parent_page_title=parent_page_title,
            schemas=list(set(schema)),
            additional_databases=list(set(dependency_db)),
            progress_tracker=progress_tracker,
            use_concurrency=use_concurrency,
            max_concurrency=max_concurrency,
        )
