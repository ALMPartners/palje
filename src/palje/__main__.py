# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

import getpass
import sys
from argparse import ArgumentParser

from palje import storage_format
from palje.confluence_rest import ConfluenceREST, ConfluenceRESTError
from palje.mssql_database import MSSQLDatabase, DATABASE_OBJECT_TYPES

# TODO: move palje core functions into their own file and leave only CLI related stuff here
# TODO: setup and use logging instead of print

def _ask_db_credentials(
    server: str, database: str, authentication: str
) -> tuple[str, str]:
    """Ask the user for database credentials"""
    if authentication == "Windows":
        return ("", "")
    uid = input(f"Username for {server}.{database}: ")
    if authentication == "AAD":
        pwd = ""
    else:
        pwd = getpass.getpass(f"Password for user {uid}: ")
    return (uid, pwd)

def _ask_confluence_credentials(space_key: str) -> tuple[str, str]:
    """Ask the user for Confluence credentials"""
    uid = input(f"Confluence user for space {space_key}: ")
    password = getpass.getpass(f"Atlassian API token for user {uid}: ")
    return (uid, password)


def main(argv: list[str] | None = None):
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
    ) = parse_arguments(argv)
    # ============ DATABASE CONNECTION ============
    if authentication == "Windows":
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
        print(f"Database '{database_client.database}' was not found on the server. Did you mean '{[db for db in available_databases if db.lower() == database_client.database.lower()][0]}'?")
        quit()

    # =========== CONFLUENCE CONNECTION ===========
    confluence_client = ConfluenceREST(confluence_url)
    confluence_client.user_id, confluence_client.api_token = _ask_confluence_credentials(space_key)
    # TODO: is this test needed here? In practice, the followin get_space_id does the same.
    try:
        confluence_client.test_confluence_access(
            confluence_user_id=confluence_client.user_id,
            confluence_api_token=confluence_client.api_token,
            space_key=space_key
        )
    except ConfluenceRESTError as err:
        print(
            f"Can't access {space_key} with given credentials."
            + f" Check your username, password and Confluence URL."
        )
        quit()

    space_id = confluence_client.get_space_id(space_key)
    if not space_id:
        print(f"Failed to retrieve the id of space {space_key}. Aborting.")
        quit()

    # ============ SCHEMAS TO DOCUMENT ============
    schemas = collect_schemas_to_document(database_client, schema_filter)
    # ==== DATABASES WHERE TO SEEK DEPENDENCIES ===

    dep_databases = collect_databases_to_query_dependencies(
        database_client, database_filter, available_databases
    )
    print("--------------------------")
    print(
        f"Object dependencies are queried from the following databases: "
        + f"{', '.join(dep_databases)}"
    )
    print("--------------------------")
    # ================= ROOT PAGE =================
    root_page_id = create_or_update_root_page(
        database_client, confluence_client, space_id, parent_page
    )
    # ================ OTHER PAGES ================
    create_or_update_subpages(
        database_client,
        confluence_client,
        space_id,
        schemas,
        dep_databases,
        root_page_id,
    )


def create_or_update_subpages(
    database_client, confluence_client, space_id, schemas, dep_databases, root_page_id
):
    for schema in schemas:
        schema_page_id = create_and_update_schema_page(
            database_client, confluence_client, space_id, root_page_id, schema
        )
        objects = collect_objects_to_document(database_client, schema)
        for object_type in objects:
            type_page_id = create_and_update_object_type_page(
                database_client,
                confluence_client,
                space_id,
                schema_page_id,
                schema,
                object_type,
            )
            for object_name in objects[object_type]:
                create_and_update_object_page(
                    database_client,
                    confluence_client,
                    space_id,
                    type_page_id,
                    schema,
                    object_type,
                    object_name,
                    dep_databases,
                )


def parse_arguments(args):
    parser = ArgumentParser(
        description="A tool for creating hierarchical documentation of SQL Server databases to Confluence wiki."
    )
    parser.add_argument(
        "confluence-url",
        help='URL to Confluence REST content. In Confluence Cloud, this is something like https://<your-org>.atlassian.net/.',
    )
    parser.add_argument(
        "space",
        help="Space key of the Confluence space, in which the documentation is created.",
    )
    parser.add_argument(
        "--parent-page",
        help="Name or title of the Confluence page, under which the documentation is created. If page is not given, the documentation will be created to top level (under pages).",
    )
    parser.add_argument(
        "server", help="Host name of the SQL Server. Include port with comma."
    )
    parser.add_argument("database", help="Name of the database that is documented.")
    parser.add_argument(
        "--schemas",
        nargs="+",
        help="Names of the schemas that are documented. If not given, all schemas will be documented.",
    )
    parser.add_argument(
        "--dependent",
        nargs="+",
        help="Names of the databases, where object dependencies are sought. If not given, dependencies are sought only in documented database.",
    )
    parser.add_argument(
        "--db-driver",
        default="ODBC Driver 17 for SQL Server",
        help="Name of the database driver.",
    )
    parser.add_argument(
        "--authentication",
        default="SQL",
        help='Authentication method to database. If not provided, SQL authentication is used. Other options are "Windows" (Windwos authentication will be used) \
                             and "AAD" (Azure Active Directory login will be prompted) ',
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
        args.get("authentication", "SQL"),
    )


def collect_schemas_to_document(database_client: MSSQLDatabase, schema_filter):
    """If documented schemas not given,
    document all schemas.
    """
    all_schemas = database_client.get_schemas()
    if schema_filter:
        schemas = [s for s in schema_filter if s in all_schemas]
        schemas = list(set(schemas))
    else:
        schemas = list(set(all_schemas))  # unique database schemas
    return schemas


def collect_databases_to_query_dependencies(
    database_client: MSSQLDatabase, database_filter, available_databases
):
    """If dependent databases not given,
    track dependencies only inside documented database.
    """
    if database_filter:
        database_filter.append(
            database_client.database
        )  # add current database to filter
        dep_databases = [d for d in database_filter if d in available_databases]
        return list(set(dep_databases))
    else:
        return [database_client.database]


def collect_objects_to_document(database_client: MSSQLDatabase, schema):
    """Create dict of form
    {
        'Tables': ['table_1', 'table_2'],
        'Views': ['view_1', 'view_5'],
        ...
    }
    """
    objects = {}
    db_objects = database_client.get_objects(schema)
    for o in db_objects:
        o_type = DATABASE_OBJECT_TYPES[o["type"]]
        try:
            objects[o_type].append(o["name"])
        except:
            objects[o_type] = []
            objects[o_type].append(o["name"])
    return objects


def create_or_update_root_page(
    database_client: MSSQLDatabase,
    confluence_client: ConfluenceREST,
    space_id,
    page_name=None,
):
    """Create or update the root page of the documentation.

    If a page name is given, that will be used as the name of the root
    page. If no name is given, the default name 'DATABASE: <name-of-db>'
    is used.

    If a page already exists with the page name it and it's children
    will be updated, otherwise new pages will be created.
    """
    default_page_name = "DATABASE: " + database_client.database
    page_content = storage_format.objects_list()
    page_id = None

    if not page_name:
        page_name = default_page_name

    page_id = confluence_client.get_page_id(space_id, page_name)

    if page_id:
        confluence_client.update_page(page_id, page_name, page_content)
    else:
        page_id = confluence_client.new_page(space_id, page_name, page_content)
    return page_id


def create_and_update_schema_page(
    database_client: MSSQLDatabase,
    confluence_client: ConfluenceREST,
    space_id: str,
    root_page_id,
    schema,
):
    """First, get schema description.
    Second, check that schema page exists.
    If page exists, update it.
    Else, create schema page under root page.
    """
    schema_page_name = database_client.database + "." + schema
    description = database_client.get_schema_description(schema)
    schema_page_content = (
        storage_format.description_header(description) + storage_format.objects_list()
    )

    schema_page_id = confluence_client.get_page_id(space_id, schema_page_name)
    if schema_page_id:
        confluence_client.update_page(
            schema_page_id, schema_page_name, schema_page_content
        )
    else:
        schema_page_id = confluence_client.new_page(
            space_id, schema_page_name, schema_page_content, root_page_id
        )

    return schema_page_id


def create_and_update_object_type_page(
    database_client: MSSQLDatabase,
    confluence_client: ConfluenceREST,
    space_id: str,
    schema_page_id,
    schema,
    object_type,
):
    """First, check that object type page exists.
    If page exists, update it.
    Else, create object type page under schema page.
    """
    type_page_name = object_type + " " + database_client.database + "." + schema
    type_page_content = storage_format.objects_list()

    type_page_id = confluence_client.get_page_id(space_id, type_page_name)
    if type_page_id:
        confluence_client.update_page(type_page_id, type_page_name, type_page_content)
    else:
        type_page_id = confluence_client.new_page(
            space_id, type_page_name, type_page_content, schema_page_id
        )
    return type_page_id


def create_and_update_object_page(
    database_client: MSSQLDatabase,
    confluence_client: ConfluenceREST,
    space_id: str,
    type_page_id,
    schema,
    object_type,
    object_name,
    dep_databases,
):
    """First, create object page content.
    Second, check that object page exist.
    If page exists, update it.
    Else, create object page under object type page.
    """
    object_page_title = database_client.database + "." + schema + "." + object_name
    object_page_content = create_object_page_content(
        database_client, schema, object_type, object_name, dep_databases
    )

    object_page_id = confluence_client.get_page_id(space_id, object_page_title)
    if object_page_id:
        confluence_client.update_page(
            object_page_id,
            object_page_title,
            object_page_content,
            parent_id=type_page_id,
        )
    else:
        confluence_client.new_page(
            space_id, object_page_title, object_page_content, parent_id=type_page_id
        )


def create_object_page_content(
    database_client: MSSQLDatabase, schema, object_type, object_name, dep_databases
):
    """Object page consists of
    - Header with object description
    - For tables and views, HTML table listing
        - columns
        - their data types
        - extended properties
    - For tables and views, HTML table listing indexes
    - For procedures and functions, HTML table listing routine parameters
    - HTML table listing object dependencies in dep_databases
    """
    description = database_client.get_object_description(schema, object_name)
    object_page_content = storage_format.description_header(description)
    if object_type in ["Tables", "Views"]:
        object_columns = database_client.get_object_columns(
            schema, object_type, object_name
        )
        object_page_content += storage_format.column_table(object_columns)
        object_indexes = database_client.get_object_indexes(schema, object_name)
        object_page_content += storage_format.index_table(object_indexes)
    elif object_type in ["Procedures", "Functions"]:
        object_parameters = database_client.get_object_parameters(schema, object_name)
        object_page_content += storage_format.parameter_table(object_parameters)
    object_dependencies = database_client.get_object_dependencies(
        schema, object_name, dep_databases
    )
    object_page_content += storage_format.dependencies_table(object_dependencies)
    return object_page_content


if __name__ == "__main__":
    main(sys.argv[1:])
