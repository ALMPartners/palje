""" Legacy CLI for Palje. Kept for backwards compatibility.
    *** No new features should be added here, use cli2.py instead! ***
 """

# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import asyncio
import getpass
import sys
from argparse import ArgumentParser
from typing import Any

from palje.version import __version__ as PALJE_VERSION
from palje.confluence.confluence_rest import (
    ConfluenceRestClientAsync,
)
from palje.db_to_confluence import document_db_to_confluence_async
from palje.progress_tracker import ProgressTracker
from palje.mssql.mssql_database import MSSQLDatabaseAuthType, MSSQLDatabase

# TODO: setup and use logging instead of print


def _ask_db_credentials(
    server: str, database: str, authentication: MSSQLDatabaseAuthType
) -> tuple[str, str]:
    """Ask the user for database credentials"""
    if authentication == MSSQLDatabaseAuthType.WINDOWS:
        return ("", "")
    uid = input(f"Username for {server}.{database}: ")
    if authentication == MSSQLDatabaseAuthType.AAD:
        pwd = ""
    else:
        pwd = getpass.getpass(f"Password for user {uid}: ")
    return (uid, pwd)


def _ask_confluence_credentials(space_key: str) -> tuple[str, str]:
    """Ask the user for Confluence credentials"""
    uid = input(f"Confluence user for space {space_key}: ")
    password = getpass.getpass(f"Atlassian API token for user {uid}: ")
    return (uid, password)


def main(argv: list[Any] | None = None):
    asyncio.run(main_async(argv))


def print_progress(progress: ProgressTracker):
    """Prints a progress bar to the console."""
    bar_len = 20
    filled_len = int(round(bar_len * (progress.percents / 100.0)))
    bar = "=" * filled_len + "-" * (bar_len - filled_len)
    progress_message = (
        f"[{bar}] {progress.percents}% "
        + f"... {progress.elapsed_time:.2f}s ... {progress.message: <150}\r"
    )
    sys.stdout.write(progress_message)
    sys.stdout.flush()


async def main_async(argv: list[str] | None = None):
    # TODO: possibility to read params from config?
    (
        confluence_url,
        space_key,
        parent_page,
        server,
        database,
        schema_filter,
        database_filter,
        driver,
        authentication,
        max_concurrency,
    ) = parse_arguments(argv)

    # ============ DATABASE CONNECTION ============
    if authentication == MSSQLDatabaseAuthType.WINDOWS:
        database_client = MSSQLDatabase(
            server=server,
            database=database,
            driver=driver,
            authentication=authentication,
        )
    else:
        uid, pwd = _ask_db_credentials(
            server=server, database=database, authentication=authentication
        )
        database_client = MSSQLDatabase(
            server=server,
            database=database,
            driver=driver,
            authentication=authentication,
            username=uid,
            password=pwd,
        )

    database_client.connect()

    available_databases = database_client.get_databases()
    if database_client.database not in available_databases:
        # This happens if the database name has different case than in sys.databases
        # Find the assumed correct name and show error message to the user
        suggested_db = [
            db
            for db in available_databases
            if db.lower() == database_client.database.lower()
        ][0]
        print(
            f"Database '{database_client.database}' was not found on the server. "
            + f"Did you mean '{suggested_db}'?"
        )
        quit()

    # =========== CONFLUENCE CONNECTION ===========

    confluence_user_id, confluence_api_token = _ask_confluence_credentials(space_key)

    progress_tracker = ProgressTracker(on_step_callback=print_progress)

    async with ConfluenceRestClientAsync(
        confluence_url,
        confluence_user_id,
        confluence_api_token,
        progress_callback=progress_tracker.step,
    ) as confluence_client:
        space_accessible = await confluence_client.test_space_access(
            space_key=space_key
        )
        if not space_accessible:
            print(
                f"Can't access Confluence space {space_key} with given credentials."
                + f" Check your credentials, Confluence URL and space key."
            )
            quit()

        await document_db_to_confluence_async(
            confluence_client=confluence_client,
            db_client=database_client,
            confluence_space_key=space_key,
            parent_page_title=parent_page,
            schemas=schema_filter,
            progress_tracker=progress_tracker,
            additional_databases=database_filter,
            max_concurrency=max_concurrency,
        )

    print(f'\rExecution time: {progress_tracker.elapsed_time:.2f} seconds.{"":<150}\n')


def parse_arguments(args):
    parser = ArgumentParser(
        description="A tool for creating hierarchical documentation of SQL Server "
        + "databases to Confluence wiki.",
    )
    parser.add_argument(
        "confluence-url",
        help="URL to Confluence REST content. In Confluence Cloud, this is something "
        + "like https://<your-org>.atlassian.net/.",
    )
    parser.add_argument(
        "space",
        help="Space key of the Confluence space, in which the documentation is "
        + "created.",
    )
    parser.add_argument(
        "--parent-page",
        help="Name or title of the Confluence page, under which the documentation is"
        + "created. If page is not given, the documentation will be created to top "
        + "level (under pages).",
    )
    parser.add_argument(
        "server", help="Host name of the SQL Server. Include port with comma."
    )
    parser.add_argument("database", help="Name of the database that is documented.")
    parser.add_argument(
        "--schemas",
        nargs="+",
        help="Names of the schemas that are documented. If not given, all schemas "
        + "will be documented.",
    )
    parser.add_argument(
        "--dependent",
        nargs="+",
        help="Names of the databases, where object dependencies are sought. If not "
        + "given, dependencies are sought only in documented database.",
    )
    parser.add_argument(
        "--db-driver",
        default="ODBC Driver 17 for SQL Server",
        help="Name of the database driver.",
    )
    parser.add_argument(
        "--authentication",
        default=MSSQLDatabaseAuthType.SQL,
        choices=[at.value for at in MSSQLDatabaseAuthType],
        help="Authentication method to database. If not provided, SQL authentication "
        + 'is used. Other options are "Windows" (Windwos authentication will be used) '
        + 'and "AAD" (Azure Active Directory login will be prompted) ',
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Concurrency limit. Limits db overloading.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Palje GUI v{PALJE_VERSION}",
    )

    args = vars(parser.parse_args(args))
    return (
        args.get("confluence-url"),
        args.get("space"),
        args.get("parent_page"),
        args.get("server"),
        args.get("database"),
        args.get("schemas"),
        args.get("dependent"),
        args.get("db_driver", "ODBC Driver 17 for SQL Server"),
        MSSQLDatabaseAuthType[args.get("authentication", "SQL")],
        args.get("max_concurrency", None),
    )


if __name__ == "__main__":
    main(sys.argv[1:])
