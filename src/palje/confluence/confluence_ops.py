""" Higher level Confluence operations that build on ConfluenceRestClientAsync. """

from __future__ import annotations
import asyncio
from copy import deepcopy
import pathlib

import aiofile
from palje.confluence.confluence_models import (
    ConfluencePage,
    ConfluencePageAttachment,
    ConfluencePageHierarchy,
)
from palje.confluence.confluence_rest import (
    ConfluenceOperation,
    ConfluenceRestClientAsync,
    ConfluenceResourceType,
)
from palje.confluence.utils import construct_confluence_page_title
from palje.confluence.xml_handling import relink_gliffy_attachments
from palje.progress_tracker import ProgressTracker

# TODO: remove pass-through functions (that just call the client and do nothing else)

# Max limit for number of concurrent async operations during recursive calls
SEMAPHORE_LIMIT = 10

# region PAGE SORTING


async def reorder_page_hierarchy_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: int,
    wanted_hierarchy_root: ConfluencePage,
    page_title_prefix: str | None = None,
    page_title_postfix: str | None = None,
    recursive: bool = False,
    case_sensitive: bool = False,
    progress_tracker: ProgressTracker | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Reorder the child pages of a Confluence page.
         Optionally reorder recursively all child page hierarchies.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_id : int
        The ID of the page.

    wanted_hierarchy_root : ConfluencePage
        The root of the wanted hierarchy.

    page_title_prefix : str, optional
        The prefix to add to each title before comparison.

    page_title_postfix : str, optional
        The postfix to add to each title before comparison.

    recursive : bool, optional
        If True, reorder all child page hierarchies, too.

    case_sensitive : bool, optional
        If True, reorder with case-sensitive comparison.
        By default, all titles are lower-cased for sorting.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    semaphore : asyncio.Semaphore, optional
        An optional semaphore for limiting the number of concurrent async operations.
        If not provided, a new semaphore with a default limit is created.

    """

    if not semaphore:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    await semaphore.acquire()

    current_children = await confluence_client.get_child_pages_async(page_id)

    if progress_tracker:
        progress_tracker.target_total += len(current_children)

    if len(current_children) == 0:
        semaphore.release()
        return

    # TODO: DRY, this is somewhat the same as sort_child_pages_alphabetically_async
    # TODO: add checks e.g. what if the page count differs? or there's no matching page?
    # TODO: maybe rather use two complete hierarchies (easier to compare)?

    # Move the first page in the right place
    reference_page = wanted_hierarchy_root.child_pages[0]
    wanted_page_title = construct_confluence_page_title(
        reference_page.title, page_title_prefix, page_title_postfix
    )
    wanted_first_page = next(
        cp for cp in current_children if cp.title == wanted_page_title
    )

    current_first_page = current_children[0]
    if wanted_first_page.id != current_first_page.id:
        await confluence_client.move_page_async(
            wanted_first_page.id, "before", current_first_page.id
        )
    if progress_tracker:
        progress_tracker.step(passed=True, message=wanted_page_title)

    # Move the rest of the pages to follow the first in correct order
    last_sorted_id = wanted_first_page.id
    for page in wanted_hierarchy_root.child_pages[1:]:
        wanted_page_title = construct_confluence_page_title(
            page.title, page_title_prefix, page_title_postfix
        )
        wanted_page = next(
            child for child in current_children if child.title == wanted_page_title
        )
        await confluence_client.move_page_async(wanted_page.id, "after", last_sorted_id)
        last_sorted_id = wanted_page.id
        if progress_tracker:
            progress_tracker.step(passed=True, message=wanted_page_title)

    semaphore.release()

    if recursive:
        tasks = _create_child_page_reordering_tasks(
            confluence_client=confluence_client,
            current_children=current_children,
            wanted_hierarchy_root=wanted_hierarchy_root,
            page_title_prefix=page_title_prefix,
            page_title_postfix=page_title_postfix,
            recursive=recursive,
            case_sensitive=case_sensitive,
            progress_tracker=progress_tracker,
            semaphore=semaphore,
        )

        await asyncio.gather(*tasks)


def _create_child_page_reordering_tasks(
    confluence_client: ConfluenceRestClientAsync,
    current_children: list[ConfluencePage],
    wanted_hierarchy_root: ConfluencePage,
    page_title_prefix: str | None,
    page_title_postfix: str | None,
    recursive: bool,
    case_sensitive: bool,
    progress_tracker: ProgressTracker | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> list[asyncio.Task]:
    tasks = []
    for page in wanted_hierarchy_root.child_pages:
        wanted_page_title = construct_confluence_page_title(
            page.title, page_title_prefix, page_title_postfix
        )
        wanted_page = next(
            child for child in current_children if child.title == wanted_page_title
        )
        tasks.append(
            reorder_page_hierarchy_async(
                confluence_client=confluence_client,
                page_id=wanted_page.id,
                wanted_hierarchy_root=page,
                page_title_prefix=page_title_prefix,
                page_title_postfix=page_title_postfix,
                recursive=recursive,
                case_sensitive=case_sensitive,
                progress_tracker=progress_tracker,
                semaphore=semaphore,
            )
        )
    return tasks


def _create_child_page_alphasorting_tasks(
    confluence_client: ConfluenceRestClientAsync,
    child_pages: list[ConfluencePage],
    recursive: bool,
    case_sensitive: bool,
    progress_tracker: ProgressTracker | None = None,
) -> list[asyncio.Task]:
    tasks = []
    for page in child_pages:
        tasks.append(
            sort_child_pages_alphabetically_async(
                confluence_client=confluence_client,
                page_id=page.id,
                recursive=recursive,
                case_sensitive=case_sensitive,
                progress_tracker=progress_tracker,
            )
        )
    return tasks


async def sort_child_pages_alphabetically_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: int,
    recursive: bool = False,
    case_sensitive: bool = False,
    progress_tracker: ProgressTracker | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Sort the child pages of a Confluence page alphabetically. Optionally sort
    recursively all child page hierarchies.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_id : int
        The ID of the page whose children are to be sorted.

    recursive : bool, optional
        If True, sort all child page hierarchies, too.
        By default, only the direct children are sorted.

    case_sensitive : bool, optional
        If True, sort with case-sensitive comparison.
        By default, all titles are lower-cased for sorting.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker

    semaphore : asyncio.Semaphore, optional
        An optional semaphore for limiting the number of concurrent async operations.
        If not provided, a new semaphore with a default limit is created.

    """

    # TODO: DRY, this is somewhat the same as reorder_page_hierarchy_async

    if not semaphore:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    await semaphore.acquire()

    child_pages = await confluence_client.get_child_pages_async(page_id)

    if progress_tracker:
        progress_tracker.target_total += len(child_pages)

    if len(child_pages) == 0:
        if progress_tracker and len(child_pages) == 1:
            progress_tracker.step(passed=True, message="no children")
        semaphore.release()
        return

    sorted_children = deepcopy(child_pages)
    if case_sensitive:
        sorted_children.sort(key=lambda x: x.title)
    else:
        sorted_children.sort(key=lambda x: x.title.lower())

    # Move the first page in the right place
    wanted_first_page = sorted_children[0]
    current_first_page = child_pages[0]
    if wanted_first_page.id != current_first_page.id:
        await confluence_client.move_page_async(
            wanted_first_page.id, "before", current_first_page.id
        )
    if progress_tracker:
        progress_tracker.step(passed=True, message=wanted_first_page.title)

    # Move the rest of the pages after the first in correct order
    last_sorted_id = wanted_first_page.id
    for page in sorted_children[1:]:
        await confluence_client.move_page_async(page.id, "after", last_sorted_id)
        last_sorted_id = page.id
        if progress_tracker:
            progress_tracker.step(passed=True, message=page.title)

    semaphore.release()

    if recursive:
        sorting_tasks = _create_child_page_alphasorting_tasks(
            confluence_client=confluence_client,
            child_pages=sorted_children,
            recursive=recursive,
            case_sensitive=case_sensitive,
            progress_tracker=progress_tracker,
        )
        await asyncio.gather(*sorting_tasks)


# endregion

# region PAGE HIERARCHIES


async def get_confluence_page_hierarchy_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: int,
    progress_tracker: ProgressTracker | None = None,
) -> ConfluencePageHierarchy:
    """Get a Confluence page hierarchy starting from a given page. Recursively fetch
    all child pages.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_id : int
        The ID of the root page of the hierarchy.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    """
    root_page = await confluence_client.get_page_by_id_async(page_id)
    parent_page = ConfluencePage(
        id=root_page.id,
        title=root_page.title,
        child_pages=[],
    )
    await _recursively_fetch_child_pages_async(
        confluence_client, parent_page, progress_tracker
    )
    return ConfluencePageHierarchy(root_page=parent_page)


def _create_child_page_fetcher_tasks(
    confluence_client: ConfluenceRestClientAsync,
    pages: list[ConfluencePage],
    progress_tracker: ProgressTracker | None = None,
):
    """Create async tasks for fetching child pages.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    pages : list[ConfluencePage]
        A list pages to expand.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    Returns
    -------

    tasks : list[Coroutine]
        A list of async tasks.

    """
    tasks = []
    for page in pages:
        tasks.append(
            _recursively_fetch_child_pages_async(
                confluence_client=confluence_client,
                parent_page=page,
                progress_tracker=progress_tracker,
            )
        )
    return tasks


async def _recursively_fetch_child_pages_async(
    confluence_client: ConfluenceRestClientAsync,
    parent_page: ConfluencePage,
    progress_tracker: ProgressTracker | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Recursively expand given ConfluencePage with all its underlying children.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    parent_page : ConfluencePage
        The parent page to expand.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    """

    if not semaphore:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    await semaphore.acquire()
    child_pages = await confluence_client.get_child_pages_async(parent_page.id)
    semaphore.release()

    if progress_tracker:
        progress_tracker.step(passed=True)
        progress_tracker.target_total += len(child_pages)

    for child_page in child_pages:
        page = ConfluencePage(
            id=child_page.id,
            title=child_page.title,
            child_pages=[],
            parent_page=parent_page,
        )
        parent_page._child_pages.append(page)

    tasks = _create_child_page_fetcher_tasks(
        confluence_client=confluence_client,
        pages=parent_page._child_pages,
        progress_tracker=progress_tracker,
    )
    await asyncio.gather(*tasks)


# endregion

# region PERMISSION CHECKS


async def is_page_deletion_allowed_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: str,
) -> bool:
    """Check if a page allows deletion.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_id : str
        The ID of the page.

    Returns
    -------
    bool
        True if the page allows deletion.

    """
    permitted_ops = await confluence_client.get_permitted_operations_on_resource_async(
        ConfluenceResourceType.PAGE, page_id
    )
    return {
        "operation": ConfluenceOperation.DELETE.value,
        "targetType": ConfluenceResourceType.PAGE.value,
    } in permitted_ops


async def is_page_creation_allowed_async(
    confluence_client: ConfluenceRestClientAsync,
    space_key: str,
) -> bool:
    """Check if a space allows page creation.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    space_key : str
        The key of the space.

    Returns
    -------

    bool
        True if the space allows page creation.
    """
    space_id = await confluence_client.get_space_id_async(space_key)
    if not space_id:
        return False
    permitted_ops = await confluence_client.get_permitted_operations_on_resource_async(
        ConfluenceResourceType.SPACE, space_id
    )
    return {
        "operation": ConfluenceOperation.CREATE.value,
        "targetType": ConfluenceResourceType.PAGE.value,
    } in permitted_ops


# endregion

# region PAGE CRUD


async def get_confluence_page_by_id_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: int,
) -> ConfluencePage:
    """Get a Confluence page by ID.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync

    page_id : int
        The ID of the page.

    Returns
    -------

    ConfluencePage
        Details of the Confluence page with the given ID.

    """
    page_data = await confluence_client.get_page_by_id_async(page_id)
    return ConfluencePage(id=page_data.id, title=page_data.title, child_pages=[])


async def get_confluence_page_by_title_async(
    confluence_client: ConfluenceRestClientAsync,
    page_title: str,
    space_key: str,
) -> ConfluencePage:
    """Get a Confluence page by title and space key.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_title : str
        The title of the page.

    space_key : str
        The key of the space.

    Returns
    -------

    ConfluencePage
        Details of the Confluence page with the given title in the given space.

    """
    space_id = await confluence_client.get_space_id_async(space_key)
    page_result = await confluence_client.get_page_by_title_async(
        space_id=space_id, page_title=page_title
    )
    return ConfluencePage(
        id=page_result.id,
        title=page_result.title,
        child_pages=[],
        body_content=page_result.body_content,
        body_format=page_result.body_format,
    )


async def create_confluence_page_async(
    confluence_client: ConfluenceRestClientAsync, space_key: str, page: ConfluencePage
) -> str:
    """Create a Confluence page.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    space_key : str
        The key of the space.

    page : ConfluencePage
        The page to create.

    Returns
    -------

    str
        The ID of the created page.

    """
    space_id = await confluence_client.get_space_id_async(space_key)
    page_id = await confluence_client.create_page_async(space_id=space_id, page=page)
    return page_id


async def update_confluence_page_async(
    confluence_client: ConfluenceRestClientAsync, page: ConfluencePage
) -> None:
    """Update a Confluence page.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page : ConfluencePage
        The page object with updated data.

    """
    await confluence_client.update_page_async(
        page_id=page.id,
        page_title=page.title,
        page_content=page.body_content,
        parent_id=page.parent_page.id if page.parent_page else None,
    )


async def upsert_confluence_page_async(
    confluence_client: ConfluenceRestClientAsync, space_key: str, page: ConfluencePage
) -> str:
    """Create or update a Confluence page.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    space_key : str
        The key of the space.

    page : ConfluencePage
        The page to create or update.

    Returns
    -------

    str
        The ID of the created or updated page.

    """
    space_id = await confluence_client.get_space_id_async(space_key)
    page_id = await confluence_client.upsert_page_async(
        space_id=space_id,
        page_title=page.title,
        page_content=page.body_content,
        parent_page_id=page.parent_page.id if page.parent_page else None,
    )
    return page_id


async def delete_confluence_pages_async(
    confluence_client: ConfluenceRestClientAsync,
    pages: list[ConfluencePage],
    progress_tracker: ProgressTracker | None = None,
) -> None:
    """Delete a list of Confluence pages.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    pages : list[ConfluencePage]
        A list of pages to delete.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker
    """
    if progress_tracker:
        progress_tracker.target_total = len(pages)

    #
    # Notice that the deletion is done ~synchronously / page by page.
    # This is really SLOW.
    #
    # It would be much more efficient to do this with parallel async tasks, but
    # unfortunately Confluence API seems to give occasional 500s when doing this.
    # This may be due to some internal book-keeping of nested pages and/or
    # Confluence's delete vs. purge feature.
    #
    # Maybe the parallel page deletion could be ran 2-3 times in a row (for pages
    # resulting in 500s) to ensure that all pages get deleted eventually?
    #
    # tasks = create_page_deletion_tasks(confluence_client, pages)
    # await asyncio.gather(*tasks)
    #
    for page in pages:
        await confluence_client.delete_page_async(page)
        if progress_tracker:
            progress_tracker.step(passed=True, message=page.title)


# def create_page_deletion_tasks(
#     confluence_client: ConfluenceRestClientAsync, pages: list[ConfluencePage]
# ) -> list[Coroutine]:
#     """Create a list of async tasks for deleting pages."""
#     tasks = []
#     for page in pages:
#         tasks.append(confluence_client.delete_page_async(page.page_id))
#     return tasks


# endregion


# region PAGE ATTACHMENTS


async def get_page_attachments_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: int,
) -> list[str]:
    """Get a list of attachments for a Confluence page.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_id : int
        The ID of the page.

    Returns
    -------

    list[str]
        A list of attachment filenames.

    """
    return await confluence_client.get_page_attachments(page_id)


async def download_attachments_async(
    confluence_client: ConfluenceRestClientAsync,
    attachments: list[dict],
    download_dir: pathlib.Path,
) -> list[ConfluencePageAttachment]:
    """Download a list of attachments from a Confluence page.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    attachments : list[dict]
        A list of attachment data.

    download_dir : pathlib.Path
        The directory where the attachments are downloaded.

    Returns
    -------
    list[ConfluencePageAttachment]
        A list of ConfluencePageAttachment objects.

    """
    # TODO: use more descriptive class for attachment instead of dict magic
    # TODO: do as async tasks
    new_attachments: list[ConfluencePageAttachment] = []
    for attachment in attachments:
        data = await confluence_client.download_file_async(attachment["downloadLink"])
        async with aiofile.async_open(
            download_dir / attachment["title"], "wb"
        ) as outfile:
            await outfile.write(data)
        new_attachments.append(
            ConfluencePageAttachment(
                title=attachment["title"],
                file_path=download_dir / attachment["title"],
                content_type=attachment["mediaType"],
            )
        )
    return new_attachments


async def upload_attachments_async(
    confluence_client: ConfluenceRestClientAsync,
    page_id: int,
    attachments: list[ConfluencePageAttachment],
) -> None:
    """Upload a list of attachments to a Confluence page.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_id : int
        The ID of the page to which the attachments are uploaded.

    attachments : list[ConfluencePageAttachment]
        A list of attachments to upload.

    """
    # TODO: do as async tasks
    for attachment in attachments:
        await confluence_client.upsert_page_attachment_async(page_id, attachment)


# region PAGE COPYING


async def copy_confluence_pages_async(
    root_page: ConfluencePage,
    confluence_space_key: str,
    src_confluence_client: ConfluenceRestClientAsync,
    tgt_confluence_client: ConfluenceRestClientAsync,
    target_confluence_space_key: str,
    work_dir: pathlib.Path,
    page_id: int | None = None,
    copy_children: bool = True,
    page_title_prefix: str = "",
    page_title_postfix: str = "",
    progress_tracker: ProgressTracker | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> int:
    """Copy a Confluence page and optionally its child pages (hierarchies).

    Arguments
    ---------
    root_page : ConfluencePage
        The root page to copy.

    confluence_space_key : str
        The key of the source space.

    src_confluence_client : ConfluenceRestClientAsync
        The source Confluence client.

    tgt_confluence_client : ConfluenceRestClientAsync
        The target Confluence client.

    target_confluence_space_key : str
        The key of the target space.

    work_dir : pathlib.Path
        The working directory for temporary files.

    page_id : int, optional
        The ID of the parent page in the target space.

    copy_children : bool, optional
        If True, recursively copy all child pages, too.

    page_title_prefix : str, optional
        The prefix to add to each page title.

    page_title_postfix : str, optional
        The postfix to add to each page title.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    semaphore : asyncio.Semaphore, optional
        An optional semaphore for limiting the number of concurrent async operations.
        If not provided, a new semaphore with a default limit is created.

    Returns
    -------

    int
        The ID of the copied page.

    """

    if not semaphore:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    await semaphore.acquire()

    page_to_copy = await get_confluence_page_by_title_async(
        confluence_client=src_confluence_client,
        space_key=confluence_space_key,
        page_title=root_page.title,
    )

    page_work_dir = work_dir.absolute() / f"{page_to_copy.id}"
    if not page_work_dir.exists():
        page_work_dir.mkdir(parents=True)

    # FIXME: create the dir only if there are attachments
    page_attachments_dir = pathlib.Path(page_work_dir) / "__attachments"
    if not page_attachments_dir.exists():
        page_attachments_dir.mkdir(parents=True)

    attachment_results = await get_page_attachments_async(
        confluence_client=src_confluence_client,
        page_id=page_to_copy.id,
    )

    attachments = await download_attachments_async(
        confluence_client=src_confluence_client,
        attachments=attachment_results["results"],
        download_dir=page_attachments_dir,
    )

    placeholder_parent: ConfluencePage | None = None
    if page_id:
        placeholder_parent = ConfluencePage(id=page_id, title="placeholder_parent")

    new_page_title = construct_confluence_page_title(
        page_to_copy.title, page_title_prefix, page_title_postfix
    )

    page_copy = ConfluencePage(
        id=None,
        title=new_page_title,
        body_content=page_to_copy.body_content,
        body_format=page_to_copy.body_format,
        parent_page=placeholder_parent,
    )

    new_page_id = await upsert_confluence_page_async(
        confluence_client=tgt_confluence_client,
        space_key=target_confluence_space_key,
        page=page_copy,
    )

    # FIXME: filenames must be checked (now e.g. " " -> "%20")
    await upload_attachments_async(
        confluence_client=tgt_confluence_client,
        page_id=int(new_page_id),
        attachments=attachments,
    )

    new_attachment_results = await get_page_attachments_async(
        confluence_client=tgt_confluence_client,
        page_id=new_page_id,
    )

    # TODO: other attachment types
    updated_page_content = relink_gliffy_attachments(
        page_content=page_copy.body_content, attachments=new_attachment_results
    )

    updated_page = ConfluencePage(
        id=new_page_id,
        title=new_page_title,
        body_content=updated_page_content,
        body_format=page_copy.body_format,
        parent_page=page_copy.parent_page,
    )

    await update_confluence_page_async(
        confluence_client=tgt_confluence_client,
        page=updated_page,
    )

    if progress_tracker:
        progress_tracker.step(passed=True, message=new_page_title)

    semaphore.release()

    if copy_children and root_page.child_pages:
        tasks = []
        for child_page in root_page.child_pages:
            co = copy_confluence_pages_async(
                root_page=child_page,
                src_confluence_client=src_confluence_client,
                confluence_space_key=confluence_space_key,
                tgt_confluence_client=tgt_confluence_client,
                target_confluence_space_key=target_confluence_space_key,
                page_id=new_page_id,
                copy_children=copy_children,
                work_dir=page_work_dir,
                page_title_prefix=page_title_prefix,
                page_title_postfix=page_title_postfix,
                progress_tracker=progress_tracker,
                semaphore=semaphore,
            )
            tasks.append(co)
        await asyncio.gather(*tasks)

    return new_page_id


# endregion


async def check_for_duplicate_page_titles_async(
    confluence_client: ConfluenceRestClientAsync,
    space_key: str,
    page_titles: list[str],
    page_title_prefix: str | None = None,
    page_title_postfix: str | None = None,
    case_sensitive: bool = False,
) -> list[str]:
    """Compare and get duplicate page titles between a Confluence space and given
    list of titles.

    Page titles in given list are adjusted with optional prefix and/or postfix
    before comparison.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync

    space_key : str
        The key of the space.

    page_titles : list[str]
        A list of page titles.

    page_title_prefix : str, optional
        The prefix to add to each title before comparison.

    page_title_postfix : str, optional
        The postfix to add to each title before comparison.

    case_sensitive : bool, optional
        If True, compare with case-sensitive comparison.
        By default, all titles are lower-cased for comparison.

    Returns
    -------
    list[str]
        A list of duplicate page titles.

    """

    target_space_id = await confluence_client.get_space_id_async(space_key=space_key)
    existing_pages = await confluence_client.get_pages_in_space_async(
        space_id=target_space_id
    )

    existing_page_titles = []
    for ep in existing_pages:
        if not case_sensitive:
            existing_page_titles.append(ep.title.lower())
        else:
            existing_page_titles.append(ep.title)

    adjusted_page_titles = []
    for pt in page_titles:
        if not case_sensitive:
            adjusted_page_titles.append(
                construct_confluence_page_title(
                    title=pt.lower(),
                    prefix=page_title_prefix,
                    postfix=page_title_postfix,
                )
            )
        else:
            adjusted_page_titles.append(
                construct_confluence_page_title(
                    title=pt, prefix=page_title_prefix, postfix=page_title_postfix
                )
            )

    duplicates = []
    for pt in adjusted_page_titles:
        if pt in existing_page_titles:
            duplicates.append(pt)

    return duplicates
