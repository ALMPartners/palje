# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

import sys
from argparse import ArgumentParser

from . import storage_format
from .confluence_rest import ConfluenceREST
from .mssql_database import MSSQLDatabase, DATABASE_OBJECT_TYPES


def main(argv):
    global WIKI, DB, SPACE, space_id
    # TODO: possibility to read params from config?
    (confluence_url, SPACE, parent_page, server, database,
        schema_filter, database_filter, driver, authentication) = parse_arguments(argv)
    # ============ DATABASE CONNECTION ============
    DB = MSSQLDatabase(server, database, driver, authentication)
    DB.connect()
    # =========== CONFLUENCE CONNECTION ===========
    WIKI = ConfluenceREST(confluence_url)
    WIKI.verify_credentials()
    space_id = WIKI.get_space_id(SPACE)
    if not space_id:
        print(f'Failed to retrieve the id of space {SPACE}. Aborting.')
        quit()
    # ============ SCHEMAS TO DOCUMENT ============
    schemas = collect_schemas_to_document(schema_filter)
    # ==== DATABASES WHERE TO SEEK DEPENDENCIES ===
    dep_databases = collect_databases_to_query_dependencies(database_filter)
    print("--------------------------")
    print(f"Object dependencies are queried from the following databases: " +
          f"{', '.join(dep_databases)}")
    print("--------------------------")
    # ================= ROOT PAGE =================
    root_page_id = create_or_update_root_page(space_id, parent_page)
    # ================ OTHER PAGES ================
    for schema in schemas:
        schema_page_id = create_and_update_schema_page(root_page_id, schema)
        objects = collect_objects_to_document(schema)
        for object_type in objects:
            type_page_id = create_and_update_object_type_page(
                schema_page_id, schema, object_type)
            for object_name in objects[object_type]:
                create_and_update_object_page(
                    type_page_id, schema, object_type, object_name, dep_databases)


def parse_arguments(args):
    parser = ArgumentParser(
        description='A tool for creating hierarchical documentation of SQL Server databases to Confluence wiki.')
    parser.add_argument('confluence-url',
                        help='URL to Confluence REST content. In Confluence Cloud, this is something like https://yourconfluence.atlassian.net/wiki/rest/api/content.')
    parser.add_argument('space',
                        help='Space key of the Confluence space, in which the documentation is created.')
    parser.add_argument('--parent-page',
                        help='Name or title of the Confluence page, under which the documentation is created. If page is not given, the documentation will be created to top level (under pages).')
    parser.add_argument('server',
                        help='Host name of the SQL Server. Include port with comma.')
    parser.add_argument('database',
                        help='Name of the database that is documented.')
    parser.add_argument('--schemas', nargs='+',
                        help='Names of the schemas that are documented. If not given, all schemas will be documented.')
    parser.add_argument('--dependent', nargs='+',
                        help='Names of the databases, where object dependencies are sought. If not given, dependencies are sought only in documented database.')
    parser.add_argument('--db-driver', default="ODBC Driver 17 for SQL Server",
                        help='Name of the database driver.')
    parser.add_argument('--authentication', default="SQL",
                        help='Authentication method to database. If not provided, SQL authentication is used. Other options are "Windows" (Windwos authentication will be used) \
                             and "AAD" (Azure Active Directory login will be prompted) ')
    args = vars(parser.parse_args(args))
    return (
        args.get('confluence-url'),
        args.get('space'),
        args.get('parent_page'),
        args.get('server'),
        args.get('database'),
        args.get('schemas'),
        args.get('dependent'),
        args.get('db_driver', 'ODBC Driver 17 for SQL Server'),
        args.get('authentication', 'SQL')
    )


def collect_schemas_to_document(schema_filter):
    """If documented schemas not given,
    document all schemas.
    """
    all_schemas = DB.get_schemas()
    if schema_filter:
        schemas = [s for s in schema_filter if s in all_schemas]
        schemas = list(set(schemas))
    else:
        schemas = list(set(all_schemas))  # unique database schemas
    return schemas


def collect_databases_to_query_dependencies(database_filter):
    """If dependent databases not given,
    track dependencies only inside documented database.
    """
    if database_filter:
        server_databases = DB.get_databases()
        database_filter.append(DB.database)  # add current database to filter
        dep_databases = [d for d in database_filter if d in server_databases]
        return list(set(dep_databases))
    else:
        return [DB.database]


def collect_objects_to_document(schema):
    """Create dict of form
    {
        'Tables': ['table_1', 'table_2'],
        'Views': ['view_1', 'view_5'],
        ...
    }
    """
    objects = {}
    db_objects = DB.get_objects(schema)
    for o in db_objects:
        o_type = DATABASE_OBJECT_TYPES[o['type']]
        try:
            objects[o_type].append(o['name'])
        except:
            objects[o_type] = []
            objects[o_type].append(o['name'])
    return objects


def create_or_update_root_page(space_id, page_name=None):
    """Create or update the root page of the documentation.

    If a page name is given, that will be used as the name of the root
    page. If no name is given, the default name 'DATABASE: <name-of-db>'
    is used.

    If a page already exists with the page name it and it's children
    will be updated, otherwise new pages will be created.
    """
    default_page_name = 'DATABASE: ' + DB.database
    page_content = storage_format.objects_list()
    page_id = None

    if not page_name:
        page_name = default_page_name

    page_id = WIKI.get_page_id(space_id, page_name)

    if page_id:
        WIKI.update_page(page_id, page_name, page_content)
    else:
        page_id = WIKI.new_page(space_id, page_name, page_content)
    return page_id


def create_and_update_schema_page(root_page_id, schema):
    """First, get schema description.
    Second, check that schema page exists.
    If page exists, update it.
    Else, create schema page under root page.
    """
    schema_page_name = DB.database + '.' + schema
    description = DB.get_schema_description(schema)
    schema_page_content = storage_format.description_header(description) + \
        storage_format.objects_list()

    schema_page_id = WIKI.get_page_id(space_id, schema_page_name)
    if schema_page_id:
        WIKI.update_page(schema_page_id, schema_page_name, schema_page_content)
    else:
        schema_page_id = WIKI.new_page(
            space_id, schema_page_name, schema_page_content, root_page_id)

    return schema_page_id


def create_and_update_object_type_page(schema_page_id, schema, object_type):
    """First, check that object type page exists.
    If page exists, update it.
    Else, create object type page under schema page.
    """
    type_page_name = object_type + ' ' + DB.database + '.' + schema
    type_page_content = storage_format.objects_list()

    type_page_id = WIKI.get_page_id(space_id, type_page_name)
    if type_page_id:
        WIKI.update_page(type_page_id, type_page_name, type_page_content)
    else:
        type_page_id = WIKI.new_page(
            space_id, type_page_name, type_page_content, schema_page_id)
    return type_page_id


def create_and_update_object_page(
        type_page_id, schema, object_type, object_name, dep_databases):
    """First, create object page content.
    Second, check that object page exist.
    If page exists, update it.
    Else, create object page under object type page.
    """
    object_page_title = DB.database + '.' + schema + '.' + object_name
    object_page_content = create_object_page_content(
        schema, object_type, object_name, dep_databases)

    object_page_id = WIKI.get_page_id(space_id, object_page_title)
    if object_page_id:
        WIKI.update_page(object_page_id, object_page_title,
                         object_page_content, parent_id=type_page_id)
    else:
        WIKI.new_page(space_id, object_page_title,
                      object_page_content, parent_id=type_page_id)


def create_object_page_content(schema, object_type, object_name, dep_databases):
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
    description = DB.get_object_description(schema, object_name)
    object_page_content = storage_format.description_header(description)
    if object_type in ['Tables', 'Views']:
        object_columns = DB.get_object_columns(
            schema, object_type, object_name)
        object_page_content += storage_format.column_table(object_columns)
        object_indexes = DB.get_object_indexes(schema, object_name)
        object_page_content += storage_format.index_table(object_indexes)
    elif object_type in ['Procedures', 'Functions']:
        object_parameters = DB.get_object_parameters(schema, object_name)
        object_page_content += storage_format.parameter_table(
            object_parameters)
    object_dependencies = DB.get_object_dependencies(
        schema, object_name, dep_databases)
    object_page_content += storage_format.dependencies_table(
        object_dependencies)
    return object_page_content


if __name__ == "__main__":
    main(sys.argv[1:])
