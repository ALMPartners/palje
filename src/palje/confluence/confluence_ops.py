""" Higher level Confluence operations that build on ConfluenceRestClientAsync. """

import asyncio
from palje.confluence.confluence_rest import (
    ConfluenceOperation,
    ConfluenceRestClientAsync,
    ConfluenceResourceType,
)
from palje.progress_tracker import ProgressTracker


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


async def get_confluence_page_id_by_title(
    confluence_url: str,
    uid: str,
    api_token: str,
    page_title: str,
    space_key: str,
) -> int:
    """Get the ID of a Confluence page by title and space key.

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
    int
        The ID of the page.

    """
    async with ConfluenceRestClientAsync(
        confluence_url, uid, api_token
    ) as confluence_client:
        space_id = await confluence_client.get_space_id_async(space_key)
        return await confluence_client.get_page_id_async(
            space_id=space_id, page_title=page_title
        )


async def get_nested_confluence_page_ids_async(
    confluence_url: str,
    uid: str,
    api_token: str,
    parent_page_id: int,
    progress_tracker: ProgressTracker | None = None,
) -> None:
    """Get the IDs of a page and all its children recursively.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    parent_page_id : int
        The ID of the parent page.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.


    Returns
    -------

    page_ids : list[int]
        A list of page IDs.

    """
    async with ConfluenceRestClientAsync(
        confluence_url,
        uid,
        api_token,
        progress_callback=progress_tracker.step if progress_tracker else None,
    ) as confluence_client:
        recursive_children = await get_recursive_confluence_child_page_ids_async(
            confluence_client, parent_page_id, progress_tracker=progress_tracker
        )
        page_ids = [int(child) for child in recursive_children]
        page_ids.append(parent_page_id)
    return page_ids


def create_page_child_page_finder_tasks(
    confluence_client: ConfluenceRestClientAsync,
    page_ids: list[int],
    results: list[int],
    progress_tracker: ProgressTracker | None = None,
):
    """Create a list of async tasks for finding child pages.

    Arguments
    ---------
    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    page_ids : list[int]
        A list of page IDs to find child pages for.

    results : list[int]
        A list to store the results.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    Returns
    -------

    tasks : list[Coroutine]
        A list of async tasks.

    """
    tasks = []
    for page_id in page_ids:
        tasks.append(
            get_recursive_confluence_child_page_ids_async(
                confluence_client, page_id, results, progress_tracker
            )
        )
    return tasks


# TODO: move to client?
async def get_recursive_confluence_child_page_ids_async(
    confluence_client: ConfluenceRestClientAsync,
    parent_page_id: int,
    results: list[int] | None = None,
    progress_tracker: ProgressTracker | None = None,
) -> list[int]:
    """Recursively find all child page ids for a page.

    Arguments
    ---------

    confluence_client : ConfluenceRestClientAsync
        The Confluence client.

    parent_page_id : int
        The ID of the parent page.

    results : list[int], optional
        A list to store the results. Leave empty to create a new list.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    Returns
    -------
    list[int]
        A list of page IDs.

    """
    results = results or []
    child_page_ids = await confluence_client.get_child_page_ids_async(parent_page_id)
    if progress_tracker:
        progress_tracker.target_total += len(child_page_ids)

    for page_id in child_page_ids:
        results.append(page_id)

    pf_tasks = create_page_child_page_finder_tasks(
        confluence_client=confluence_client,
        page_ids=child_page_ids,
        results=results,
        progress_tracker=progress_tracker,
    )
    await asyncio.gather(*pf_tasks)

    return results


async def delete_confluence_pages(
    confluence_url: str,
    uid: str,
    api_token: str,
    page_ids: list[int],
    progress_tracker: ProgressTracker | None = None,
) -> None:
    """Delete a list of Confluence pages.

    Arguments
    ---------

    confluence_url : str
        The root URL of the Confluence server.

    uid : str
        The Atlassian user id of the user.

    api_token : str
        Atlassian API token of the user.

    page_ids : list[int]
        A list of page IDs to delete.

    progress_tracker : ProgressTracker, optional
        An optional progress tracker.

    """
    if progress_tracker:
        progress_tracker.target_total = len(page_ids)

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
        # tasks = create_page_deletion_tasks(confluence_client, page_ids)
        # await asyncio.gather(*tasks)
        #
        for page_id in page_ids:
            await confluence_client.delete_page_async(page_id)


# def create_page_deletion_tasks(
#     confluence_client: ConfluenceRestClientAsync, page_ids: list[int]
# ) -> list[Coroutine]:
#     """Create a list of async tasks for deleting pages."""
#     tasks = []
#     for page_id in page_ids:
#         tasks.append(confluence_client.delete_page_async(page_id))
#     return tasks
