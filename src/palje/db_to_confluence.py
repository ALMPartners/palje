import asyncio
from typing import Coroutine
from palje.confluence import storage_format
from palje.confluence.confluence_rest import ConfluenceRestClientAsync
from palje.progress_tracker import ProgressTracker
from palje.mssql.mssql_database import MSSQLDatabase, DATABASE_OBJECT_TYPES

# Maximum number of concurrent tasks.
# The database seems to be the bottleneck. Adjust this higher if the queries can be made
# more efficient or/and less frequent.
DEFAULT_CONCURRENCY_LIMIT = 2

# region Confluence documentation writing


async def document_db_to_confluence_async(
    confluence_client: ConfluenceRestClientAsync,
    db_client: MSSQLDatabase,
    confluence_space_key: str,
    parent_page_title: str | None = None,
    schemas: list[str] | None = None,
    additional_databases: list[str] | None = None,
    progress_tracker: ProgressTracker | None = None,
    max_concurrency: int = DEFAULT_CONCURRENCY_LIMIT,
) -> None:
    """Collect documentation from the database and upload it to Confluence.

    Arguments:
    ----------

    confluence_client : ConfluenceRestClientAsync
        Confluence client instance.

    db_client : MSSQLDatabase
        Database client instance.

    confluence_space_key : str
        Confluence space key.

    parent_page_title : str, optional
        Title of the parent page. If not given, root page is created.

    schemas : list[str], optional
        List of schemas to document. If not given, all schemas are documented.

    additional_databases : list[str], optional
        List of databases to query dependencies. If not given, dependencies are sought
        only in the documented database.

    progress_tracker : ProgressTracker, optional
        Progress tracker instance. If not given, progress is not tracked.

    max_concurrency : int, optional
        Concurrency limit. Limits async task creation but even with value 1
        there is still some concurrency. Large values may overload the database.

    """

    async with confluence_client:
        confluence_space_id = await confluence_client.get_space_id_async(
            confluence_space_key
        )
        schemas = collect_schemas_to_document(db_client, schemas)

        dependent_databases = collect_databases_to_query_dependencies(
            database_client=db_client,
            available_databases=db_client.get_databases(),
            databases_to_include=additional_databases,
        )
        object_dependencies = db_client.get_object_dependencies(dependent_databases)

        root_page_title = (
            parent_page_title
            if parent_page_title
            else create_root_page_title(db_client.database)
        )

        root_page_content = storage_format.objects_list()
        progress_tracker.target_total += 1
        root_page_id = await confluence_client.upsert_page_async(
            page_title=root_page_title,
            page_content=root_page_content,
            space_id=confluence_space_id,
        )

        tasks = create_async_subpage_upsert_tasks(
            db_client,
            confluence_client,
            confluence_space_id,
            schemas,
            object_dependencies,
            root_page_id,
            progress_tracker=progress_tracker,
            max_concurrency=max_concurrency,
        )
        await asyncio.gather(*tasks)


def create_async_subpage_upsert_tasks(
    database_client: MSSQLDatabase,
    confluence_client: ConfluenceRestClientAsync,
    space_id: str,
    schemas: list[str],
    object_dependencies: dict[str, list[str]],
    root_page_id: int,
    progress_tracker: ProgressTracker | None = None,
    max_concurrency: int = DEFAULT_CONCURRENCY_LIMIT,
) -> list[Coroutine]:
    """Create async co-routines for creating or updating subpages for each
    schema in schemas.

    Arguments:
    ----------

    database_client : MSSQLDatabase
        Database client instance.

    confluence_client : ConfluenceRestClientAsync
        Confluence client instance.

    space_id : str
        Confluence space ID.

    schemas : list[str]
        List of schemas to document.

    object_dependencies : dict[str, list[str]]
        Dictionary of object dependencies.

    root_page_id : int
        ID of the root page.

    progress : ProgressTracker, optional
        Progress tracker instance. If not given, progress is not tracked.

    """

    tasks = []
    # TODO: makes no sense to have the semaphore here; it should (mainly) limit
    #       the db queries, not the confluence writes
    semaphore = asyncio.Semaphore(max_concurrency)
    for schema in schemas:
        tasks.append(
            create_or_update_subpages_async(
                database_client,
                semaphore,
                confluence_client,
                space_id,
                schema,
                object_dependencies,
                root_page_id,
                progress_tracker=progress_tracker,
            )
        )
    return tasks


def create_async_object_page_upsert_tasks(
    objects: list[str],
    object_type: str,
    database_client: MSSQLDatabase,
    confluence_client: ConfluenceRestClientAsync,
    space_id: int,
    schema: str,
    object_dependencies: dict[str, list[str]],
    parent_page_id: int,
) -> list[Coroutine]:
    """Create async tasks for batch creating/updating object pages.

    Arguments:
    ----------

    objects : dict[str, list[str]]
        Dictionary of objects to document.

    database_client : MSSQLDatabase
        Database client instance.

    confluence_client : ConfluenceRestClientAsync
        Confluence client instance.

    space_id : str
        Confluence space ID.

    schema : str
        Schema name.

    object_dependencies : dict[str, list[str]]
        Dictionary of object dependencies.

    type_page_id : int
        ID of the parent page.
    """
    tasks = []
    for object_name in objects:
        object_page_title = create_object_page_title(
            database_client.database, schema, object_name
        )
        object_page_content = create_object_page_content(
            database_client,
            schema,
            object_type,
            object_name,
            object_dependencies,
        )
        tasks.append(
            confluence_client.upsert_page_async(
                page_title=object_page_title,
                page_content=object_page_content,
                space_id=space_id,
                parent_page_id=parent_page_id,
            )
        )
    return tasks


async def create_or_update_subpages_async(
    database_client: MSSQLDatabase,
    semaphore: asyncio.Semaphore,
    confluence_client: ConfluenceRestClientAsync,
    space_id: str,
    schema: str,
    object_dependencies: dict[str, list[str]],
    root_page_id: int,
    progress_tracker: ProgressTracker | None = None,
):
    """Create or update subpages for the given schema.

    Arguments:
    ----------

    database_client : MSSQLDatabase
        Database client instance.

    semaphore : asyncio.Semaphore
        Semaphore for concurrency control.

    confluence_client : ConfluenceRestClientAsync
        Confluence client instance.

    space_id : str
        Confluence space ID.

    schema : str
        Schema name.

    object_dependencies : dict[str, list[str]]
        Dictionary of object dependencies.

    root_page_id : int
        ID of the root page.

    progress : ProgressTracker, optional
        Progress tracker instance. If not given, progress is not tracked.

    """

    async with semaphore:
        # TODO: separate db reading from confluence writing?
        # TODO: use semaphore to limit (only) db tasks?

        database_name = database_client.database
        schema_page_title = create_schema_page_title(database_name, schema)
        schema_description = database_client.get_schema_description(schema)
        schema_page_content = (
            storage_format.description_header(schema_description)
            + storage_format.objects_list()
        )
        if progress_tracker:
            progress_tracker.target_total += 1
        schema_page_id = await confluence_client.upsert_page_async(
            page_title=schema_page_title,
            page_content=schema_page_content,
            space_id=space_id,
            parent_page_id=root_page_id,
        )

        # Create object type pages (Tables, Procedures, ...)

        objects = collect_objects_to_document(database_client, schema)
        for object_type in objects:
            obj_type_page_title = create_object_type_page_title(
                database_name, schema, object_type
            )
            obj_type_page_content = storage_format.objects_list()
            if progress_tracker:
                progress_tracker.target_total += 1
            obj_type_page_id = await confluence_client.upsert_page_async(
                page_title=obj_type_page_title,
                page_content=obj_type_page_content,
                space_id=space_id,
                parent_page_id=schema_page_id,
            )

            # Create object pages under object type page

            tasks = create_async_object_page_upsert_tasks(
                objects[object_type],
                object_type,
                database_client,
                confluence_client,
                space_id,
                schema,
                object_dependencies,
                obj_type_page_id,
            )
            progress_tracker.target_total += len(tasks)

            await asyncio.gather(*tasks)


# endregion

# region Database documentation collecting


def collect_schemas_to_document(
    database_client: MSSQLDatabase, schemas_to_omit: list[str]
) -> list[str]:
    """Get a list of schemas in given database.

    Arguments:
    ----------
    database_client : MSSQLDatabase
        Database client object.

    schemas_to_omit : list[str]
        List of schemas to omit from documentation.

    Returns:
    --------

    schemas : list[str]
    """
    all_schemas = database_client.get_schemas()
    if schemas_to_omit:
        schemas = [s for s in schemas_to_omit if s in all_schemas]
        schemas = list(set(schemas))
    else:
        schemas = list(set(all_schemas))  # unique database schemas
    return schemas


# TODO: filter -> name better, make optional last parm
def collect_databases_to_query_dependencies(
    database_client: MSSQLDatabase,
    available_databases: list[str],
    databases_to_include: list[str] | None,
) -> list[str]:
    """Get a list of databases to query for dependencies.

    Arguments:
    ----------
    database_client : MSSQLDatabase
        Database client object.

    databases_to_include : list[str] | None
        List of databases to include in dependency search.

    available_databases : list[str]

    Returns:
    --------

    dep_databases : list[str]
    """
    if databases_to_include:
        databases_to_include.append(
            database_client.database
        )  # add current database to filter
        dep_databases = [d for d in databases_to_include if d in available_databases]
        return list(set(dep_databases))
    else:
        return [database_client.database]


def collect_objects_to_document(
    database_client: MSSQLDatabase, schema: str
) -> dict[str, list[str]]:
    """Get a dict of database objects in given schema.
        Returns a dict of form
        ```
        {
            'Tables': ['table_1', 'table_2'],
            'Views': ['view_1', 'view_5'],
            ...
        }
        ```

    Arguments:
    ----------
    database_client : MSSQLDatabase
        Database client object.

    schema : str
        Database schema.

    Returns:
    --------
    objects : dict[str, list[str]]

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


def create_root_page_title(database_name: str) -> str:
    """Create a title for the root page of the database documentation.

    Arguments:
    ----------
    database_name : str
        Database name.

    Returns:
    --------
    str

    """
    return f"DATABASE: {database_name}"


def create_schema_page_title(database_name: str, schema: str) -> str:
    """Create a title for the schema page of the database documentation.

    Arguments:
    ----------
    database_name : str
        Database name.

    schema : str
        Schema name.

    Returns:
    --------
    str

    """
    return database_name + "." + schema


def create_object_page_title(database_name: str, schema: str, object_name: str) -> str:
    """Create a title for the object page of the database documentation.


    Arguments:
    ----------
    database_name : str
        Database name.

    schema : str
        Schema name.

    object_name : str
        Object name.

    Returns:
    --------

    str

    """
    return database_name + "." + schema + "." + object_name


def create_object_type_page_title(
    database_name: str, schema: str, object_type: str
) -> str:
    """Create a title for the object type page of the database documentation.

    Arguments:
    ----------
    database_name : str
        Database name.

    schema : str
        Schema name.

    object_type : str
        Object type.

    Returns:
    --------

    str
    """
    return database_name + "." + schema + "." + object_type


def create_object_page_content(
    database_client: MSSQLDatabase,
    schema: str,
    object_type: str,
    object_name: str,
    object_dependencies: dict[str, list[str]],
) -> str:
    """Create content for the object page of the database documentation.

    Arguments:
    ----------

    database_client : MSSQLDatabase
        Database client object.

    schema : str
        Database schema.

    object_type : str
        Database object type. One of "Tables", "Views", "Procedures", "Functions".

    object_name : str
        Database object name.

    object_dependencies : dict[str, list[str]]
        Dictionary of object dependencies.

    Returns:
    --------

    str

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
    o = []
    for d in object_dependencies:
        if d["source"]["Object"] == object_name and d["source"]["Schema"] == schema:
            o.append(d["target"])
        elif d["target"]["Object"] == object_name and d["target"]["Schema"] == schema:
            o.append(d["source"])
    object_page_content += storage_format.dependencies_table(o)
    return object_page_content


# endregion
