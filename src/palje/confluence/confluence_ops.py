""" Higher level Confluence operations that build on ConfluenceRestClientAsync. """

from __future__ import annotations
import asyncio
from palje.confluence.confluence_models import ConfluencePage, ConfluencePageHierarchy
from palje.confluence.confluence_rest import (
    ConfluenceOperation,
    ConfluenceRestClientAsync,
    ConfluenceResourceType,
)
from palje.progress_tracker import ProgressTracker

# region PAGE HIERARCHIES


async def get_confluence_page_hierarchy_async(
    confluence_url: str,
    uid: str,
    api_token: str,
    page_id: int,
    progress_tracker: ProgressTracker | None = None,
) -> ConfluencePageHierarchy:
    """Get a hierarchy of Confluence pages.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    page_id : int
        The ID of the root page.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    Returns
    -------

    ConfluencePageHierarchy
        A hierarchy of Confluence pages.

    """
    async with ConfluenceRestClientAsync(
        confluence_url,
        uid,
        api_token,
        progress_callback=progress_tracker.step if progress_tracker else None,
    ) as confluence_client:
        root_page = await confluence_client.get_page_by_id_async(page_id)
        parent_page = ConfluencePage(
            id=root_page.id,
            title=root_page.title,
            child_pages=[],
        )
        await _recursively_expand_child_pages_async(
            confluence_client, parent_page, progress_tracker
        )
        return ConfluencePageHierarchy(root_page=parent_page)


def _create_child_page_expander_tasks(
    confluence_client: ConfluenceRestClientAsync,
    pages: list[ConfluencePage],
    progress_tracker: ProgressTracker | None = None,
):
    """Create async tasks for expanding child pages.

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
            _recursively_expand_child_pages_async(
                confluence_client=confluence_client,
                parent_page=page,
                progress_tracker=progress_tracker,
            )
        )
    return tasks


async def _recursively_expand_child_pages_async(
    confluence_client: ConfluenceRestClientAsync,
    parent_page: ConfluencePage,
    progress_tracker: ProgressTracker | None = None,
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
    child_pages = await confluence_client.get_child_pages_async(parent_page.id)
    if progress_tracker:
        progress_tracker.target_total += len(child_pages)

    for child_page in child_pages:
        page = ConfluencePage(id=child_page.id, title=child_page.title, child_pages=[])
        parent_page._child_pages.append(page)

    tasks = _create_child_page_expander_tasks(
        confluence_client=confluence_client,
        pages=parent_page._child_pages,
        progress_tracker=progress_tracker,
    )
    await asyncio.gather(*tasks)


# endregion

# region PERMISSION CHECKS


async def is_page_deletion_allowed_async(
    confluence_url: str,
    uid: str,
    api_token: str,
    page_id: str,
) -> bool:
    """Check if a page can be deleted.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    page_id : str
        The ID of the page.

    Returns
    -------

    bool
        True if the page can be deleted.

    """
    async with ConfluenceRestClientAsync(
        root_url=confluence_url, user_id=uid, api_token=api_token
    ) as confluence_client:
        permitted_ops = (
            await confluence_client.get_permitted_operations_on_resource_async(
                ConfluenceResourceType.PAGE, page_id
            )
        )
        return {
            "operation": ConfluenceOperation.DELETE.value,
            "targetType": ConfluenceResourceType.PAGE.value,
        } in permitted_ops


async def is_page_creation_allowed_async(
    confluence_url: str,
    uid: str,
    api_token: str,
    space_key: str,
) -> bool:
    """Check if a space allows page creation.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    space_key : str
        The key of the space.

    Returns
    -------

    bool
        True if the space allows page creation.
    """
    async with ConfluenceRestClientAsync(
        root_url=confluence_url, user_id=uid, api_token=api_token
    ) as confluence_client:
        space_id = await confluence_client.get_space_id_async(space_key)
        if not space_id:
            return False
        permitted_ops = (
            await confluence_client.get_permitted_operations_on_resource_async(
                ConfluenceResourceType.SPACE, space_id
            )
        )
        return {
            "operation": ConfluenceOperation.CREATE.value,
            "targetType": ConfluenceResourceType.PAGE.value,
        } in permitted_ops


# endregion Permission checks

# region SINGLE PAGE RETRIEVAL


async def get_confluence_page_by_id(
    confluence_url: str,
    uid: str,
    api_token: str,
    page_id: int,
) -> ConfluencePage:
    """Get a Confluence page by ID.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    page_id : int
        The ID of the page.

    Returns
    -------

    ConfluencePage
        The Confluence page.

    """
    async with ConfluenceRestClientAsync(
        confluence_url, uid, api_token
    ) as confluence_client:
        page_data = await confluence_client.get_page_by_id_async(page_id)
        return ConfluencePage(id=page_data.id, title=page_data.title, child_pages=[])


async def get_confluence_page_by_title(
    confluence_url: str,
    uid: str,
    api_token: str,
    page_title: str,
    space_key: str,
) -> ConfluencePage:
    """Get a Confluence page by title and space key.

    Arguments
    ---------
    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    page_title : str
        The title of the page.

    space_key : str
        The key of the space.

    Returns
    -------
    ConfluencePage
        Details of the Confluence page with the given title and space key.

    """
    async with ConfluenceRestClientAsync(
        confluence_url, uid, api_token
    ) as confluence_client:
        space_id = await confluence_client.get_space_id_async(space_key)
        page_result = await confluence_client.get_page_by_title_async(
            space_id=space_id, page_title=page_title
        )
        return ConfluencePage(
            id=page_result.id, title=page_result.title, child_pages=[]
        )


# endregion

# region PAGE DELETION


async def delete_confluence_pages(
    confluence_url: str,
    uid: str,
    api_token: str,
    pages: list[ConfluencePage],
    progress_tracker: ProgressTracker | None = None,
) -> None:
    """Delete all Confluence pages in given ConfluencePageHierarchy.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    pages : list[ConfluencePage]
        List of pages to delete.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    """
    if progress_tracker:
        progress_tracker.target_total = len(pages)

    async with ConfluenceRestClientAsync(
        confluence_url,
        uid,
        api_token,
        progress_callback=progress_tracker.step if progress_tracker else None,
    ) as confluence_client:
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


# def create_page_deletion_tasks(
#     confluence_client: ConfluenceRestClientAsync, pages: list[ConfluencePage]
# ) -> list[Coroutine]:
#     """Create a list of async tasks for deleting pages."""
#     tasks = []
#     for page in pages:
#         tasks.append(confluence_client.delete_page_async(page.page_id))
#     return tasks

# endregion
