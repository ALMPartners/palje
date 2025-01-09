from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import json
import pathlib
from typing import Coroutine

import aiofile
from palje.confluence import storage_format
from palje.confluence.confluence_ops import (
    create_confluence_page_from_file_async,
)
from palje.confluence.confluence_rest import ConfluenceRestClientAsync
from palje.confluence.utils import to_safe_filename
from palje.progress_tracker import ProgressTracker
from palje.mssql.mssql_database import MSSQLDatabase, DATABASE_OBJECT_TYPES

# region Confluence documentation writing


@dataclass
class ConfluencePageMapEntry:
    """Confluence page map entry."""

    page_title: str
    page_content_file: pathlib.Path
    child_pages: list[ConfluencePageMapEntry] = field(default_factory=list)


async def create_confluence_db_doc_files(
    db_client: MSSQLDatabase,
    output_dir: pathlib.Path,
    parent_page_title: str | None = None,
    schemas: list[str] | None = None,
    additional_databases: list[str] | None = None,
    progress_tracker: ProgressTracker | None = None,
) -> pathlib.Path:
    """Reads database metadata and creates Confluence page files out of it.


    Arguments:
    ----------

    db_client : MSSQLDatabase
        Database client instance.

    output_dir : pathlib.Path
        Output directory for the Confluence page files.

    parent_page_title : str, optional
        Title of the parent page. If not given, default title will be generated from
        the database name.

    schemas : list[str], optional
        List of schemas to document. If not given, all schemas are documented.

    additional_databases : list[str], optional
        List of databases to query dependencies. If not given, dependencies are sought
        only in the documented database.

    progress_tracker : ProgressTracker, optional
        Progress tracker instance. If not given, progress is not tracked.


    Returns:
    --------

    pathlib.Path
        Path to the generated page map json file that describes the hiearchy.
    """

    schemas = collect_schemas_to_document(db_client, schemas)

    dependent_databases = collect_databases_to_query_dependencies(
        database_client=db_client,
        available_databases=db_client.get_databases(),
        databases_to_include=additional_databases,
    )
    object_dependencies = db_client.get_object_dependencies(dependent_databases)

    # TODO: page title prefix / postfix
    root_page_title = (
        parent_page_title
        if parent_page_title
        else create_root_page_title(db_client.database)
    )
    if progress_tracker:
        progress_tracker.target_total = 1

    root_page_content = storage_format.objects_list()

    root_page_filename = output_dir / f"{to_safe_filename(root_page_title)}.txt"

    async with aiofile.async_open(root_page_filename, "w") as f:
        await f.write(root_page_content)
    if progress_tracker:
        progress_tracker.step(passed=True)

    root_page_entry = ConfluencePageMapEntry(
        page_title=root_page_title, page_content_file=root_page_filename
    )

    progress_tracker.target_total += len(schemas)

    for schema in schemas:
        schema_page_title = create_schema_page_title(db_client.database, schema)
        schema_description = db_client.get_schema_description(schema)
        schema_page_content = (
            storage_format.description_header(schema_description)
            + storage_format.objects_list()
        )

        schema_dir = output_dir / to_safe_filename(schema_page_title)
        schema_dir.mkdir(parents=True, exist_ok=True)

        schema_page_filename = schema_dir / f"{to_safe_filename(schema_page_title)}.txt"
        async with aiofile.async_open(schema_page_filename, "w") as f:
            await f.write(schema_page_content)

        schema_page_entry = ConfluencePageMapEntry(
            page_title=schema_page_title, page_content_file=schema_page_filename
        )
        root_page_entry.child_pages.append(schema_page_entry)

        if progress_tracker:
            progress_tracker.step(passed=True)

        # Create object type pages (Tables, Procedures, ...)

        objects = collect_objects_to_document(db_client, schema)
        progress_tracker.target_total += len(objects)

        for object_type in objects:

            obj_type_page_title = create_object_type_page_title(
                db_client.database, schema, object_type
            )
            obj_type_page_content = storage_format.objects_list()
            obj_type_dir = schema_dir / to_safe_filename(obj_type_page_title)
            obj_type_dir.mkdir(parents=True, exist_ok=True)
            obj_type_page_filename = (
                obj_type_dir / f"{to_safe_filename(obj_type_page_title)}.txt"
            )

            async with aiofile.async_open(obj_type_page_filename, "w") as f:
                await f.write(obj_type_page_content)
            if progress_tracker:
                progress_tracker.step(passed=True)

            object_type_page_entry = ConfluencePageMapEntry(
                page_title=obj_type_page_title, page_content_file=obj_type_page_filename
            )
            schema_page_entry.child_pages.append(object_type_page_entry)

            # Create object pages under object type page

            if progress_tracker:
                progress_tracker.target_total += len(objects[object_type])

            for object_name in objects[object_type]:
                object_page_title = create_object_page_title(
                    db_client.database, schema, object_name
                )
                object_page_content = create_object_page_content(
                    db_client,
                    schema,
                    object_type,
                    object_name,
                    object_dependencies,
                )

                object_page_dir = obj_type_dir / to_safe_filename(object_page_title)
                object_page_dir.mkdir(parents=True, exist_ok=True)

                object_page_filename = (
                    obj_type_dir / f"{to_safe_filename(object_page_title)}.txt"
                )
                async with aiofile.async_open(object_page_filename, "w") as f:
                    await f.write(object_page_content)
                if progress_tracker:
                    progress_tracker.step(passed=True)

                object_page_entry = ConfluencePageMapEntry(
                    page_title=object_page_title, page_content_file=object_page_filename
                )
                object_type_page_entry.child_pages.append(object_page_entry)

    # recursively sort the entries
    def _alpha_sort_page_entries(entry: ConfluencePageMapEntry) -> None:
        entry.child_pages = sorted(entry.child_pages, key=lambda x: x.page_title)
        for child in entry.child_pages:
            _alpha_sort_page_entries(child)

    _alpha_sort_page_entries(root_page_entry)

    # convert the page map to a hierarchical dict
    def _page_map_to_dict(entry: ConfluencePageMapEntry) -> dict:
        return {
            "page_title": entry.page_title,
            "page_content_file": str(entry.page_content_file),
            "child_pages": [_page_map_to_dict(child) for child in entry.child_pages],
        }

    page_map = _page_map_to_dict(root_page_entry)
    # write the page map to a json file
    page_map_file = output_dir / "palje_confluence_page_map.json"
    async with aiofile.async_open(page_map_file, "w") as f:
        await f.write(json.dumps(page_map))

    return page_map_file


def _create_child_page_upsert_tasks(
    confluence_client: ConfluenceRestClientAsync,
    confluence_space_id: str,
    parent_page_id: int | None,
    entry: ConfluencePageMapEntry,
    progress_tracker: ProgressTracker | None = None,
) -> list[Coroutine]:
    tasks = []

    for child in entry.child_pages:
        if progress_tracker:
            progress_tracker.target_total += 1
        tasks.append(
            create_confluence_pages_from_entries_recursively_async(
                confluence_client,
                confluence_space_id,
                parent_page_id,
                child,
                progress_tracker,
            )
        )
    return tasks


async def create_confluence_pages_from_entries_recursively_async(
    confluence_client: ConfluenceRestClientAsync,
    confluence_space_id: str,
    parent_page_id: int | None,
    page_map_root_entry: ConfluencePageMapEntry,
    progress_tracker: ProgressTracker | None = None,
) -> int:
    """Recursively creates Confluence pages from the page map entries.
       Pages are created in random order and may need to be reordered afterwards.

    Arguments:
    ----------

    confluence_client : ConfluenceRestClientAsync
        Confluence client instance.

    confluence_space_id : str
        Confluence space id.

    parent_page_id : int, optional
        ID of the parent page.

    entry : ConfluencePageMapEntry
        Page map entry. May contain child pages.

    progress_tracker : ProgressTracker, optional
        Progress tracker instance. If not given, progress is not tracked.

    Returns:
    --------

    int
        ID of the created page.

    """

    page_id = await create_confluence_page_from_file_async(
        confluence_client=confluence_client,
        page_title=page_map_root_entry.page_title,
        page_content_file=page_map_root_entry.page_content_file,
        space_id=confluence_space_id,
        parent_page_id=parent_page_id,
    )

    tasks = _create_child_page_upsert_tasks(
        confluence_client,
        confluence_space_id,
        page_id,
        page_map_root_entry,
        progress_tracker=progress_tracker,
    )

    await asyncio.gather(*tasks)

    return page_id


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
    return sorted(schemas)


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

    Arguments:
    ----------
    database_client : MSSQLDatabase
        Database client object.

    schema : str
        Database schema.

    Returns:
    --------
    dict[str, list[str]] : dict of database objects in given schema
        Example format:
        ```
        {
            'Tables': ['table_1', 'table_2'],
            'Views': ['view_1', 'view_5'],
            ...
        }
        ```

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
    return object_type + " " + database_name + "." + schema


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
        object_columns = database_client.get_object_column_info(
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
