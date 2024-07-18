from __future__ import annotations

# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from enum import Enum
import json
from typing import Callable
import aiohttp
from urllib.parse import urljoin


class ConfluenceResourceType(Enum):
    """Confluence target types."""

    PAGE = "page"
    SPACE = "space"


class ConfluenceOperation(Enum):
    """Confluence operations."""

    DELETE = "delete"
    CREATE = "create"


# TODO:
#  expection handling
#   - wrap aiohttp exceptions into ConfluenceRESTErrors to avoid
#     leaking implementation details
#
class ConfluenceRESTError(Exception):
    """Generic Confluence related exception"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ConfluenceRESTNotFoundError(ConfluenceRESTError):
    """Exception for a missing Confluence resource"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ConfluenceRESTAuthError(ConfluenceRESTError):
    """Auth related Confluence exception"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


# @dataclass
# class ConfluenceChildPageRecord:
#     """ Confluence child page result coming from children API """
#     id: str
#     status: str
#     title: str
#     spaceId: str
#     childPosition: int


class ConfluenceRestClientAsync:
    """A class for asynchronously inte racting with the Confluence REST API.

    Use the class in async context with the `async with` statement.

    Example
    -------
    ```
    async with ConfluenceRestClientAsync(
        "https://wiki.example.com",
        "username"
        "api_token"
    ) as client:
        space_id = await client.get_space_id_async("SPACE")
        page_id = await client.new_page_async(space_id, "Page title", "Page content")
        ...
    ```
    """

    _client: aiohttp.ClientSession
    _root_url: str
    _DEFAULT_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(
        self,
        root_url: str,
        user_id: str,
        api_token: str,
        headers: dict | None = None,
        progress_callback: Callable[[bool, str], None] | None = None,
    ) -> None:
        """Initialize the Confluence REST client.

        Arguments
        ---------

        root_url
            The root URL of the Confluence instance.

        user_id
            The user ID used for authentication.

        api_token
            The API token used for authentication.

        headers
            Optional headers to be used in the requests. Default headers are:
            `{"Content-Type": "application/json", "Accept": "application/json"}.`

        progress_callback
            Optional callback function that is called after each request.
            The callback function should accept [bool, str] params.
            The first one indicates if the request was succesfully completed, and
            the latter may contain some details about the operation.

        """
        self._root_url = root_url
        if headers is None:
            headers = self._DEFAULT_HEADERS
        self._client = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(login=user_id, password=api_token), headers=headers
        )
        self._progress_callback = progress_callback if progress_callback else None

    async def __aenter__(self) -> ConfluenceRestClientAsync:
        """Return the client object when entering the async context."""
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> bool | None:
        """Close the aiohttp session when exiting the async context."""
        await self._close()

    def _make_url(self, root_url, path) -> str:
        """Join the root URL and the path to form a full URL."""
        return str(urljoin(root_url, path))

    async def _close(self) -> None:
        """Close the aiohttp session."""
        return await self._client.close()

    def _update_write_progress(self, success: bool, message: str | None = None) -> None:
        """Broadcast progress via optional callback."""
        if self._progress_callback:
            self._progress_callback(success, message)

    async def get_child_page_ids_async(self, parent_page_id: int) -> list[int]:
        """Get the ids of the child pages of the given page. This is not recursive i.e.
        only the direct children of the page are returned. Due to Confluence having a
        limit (250) on the number of results per request, this method may make multiple
        requests.

        Arguments
        ---------
        parent_page_id
            The id of the parent page.

        Returns
        -------
        list[int]
            A list of the ids of the child pages. If the parent page
            has no children, an empty list is returned.
        """

        # See the current max limit for results:
        # https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-children/#api-pages-id-children-get
        MAX_RESULTS = 250

        url = self._make_url(
            self._root_url,
            f"wiki/api/v2/pages/{parent_page_id}/children?limit={MAX_RESULTS}",
        )

        has_more_children = True
        child_page_ids = []

        while has_more_children:
            try:
                async with self._client.get(url) as response:
                    response.raise_for_status()
                    if response_json := (await response.json()):
                        child_page_ids.extend(
                            [int(result["id"]) for result in response_json["results"]]
                        )
                        # If there are more children available, an iterator link to
                        # the next batch is provided in the response.
                        if (
                            "_links" in response_json
                            and "next" in response_json["_links"]
                        ):
                            url = self._make_url(
                                self._root_url, response_json["_links"]["next"]
                            )
                        else:
                            has_more_children = False
                    else:
                        has_more_children = False
            except aiohttp.ClientResponseError as e:
                if e.status == 401:
                    raise ConfluenceRESTAuthError(
                        f"Access denied for page id#{parent_page_id}."
                        + " Check your credentials."
                    ) from e
                raise ConfluenceRESTError(
                    f"Failed to fetch children for page id#{parent_page_id}."
                    + f" HTTP/{e.status}."
                ) from e
        self._update_write_progress(
            True, f"page#{parent_page_id} has {len(child_page_ids)} child pages"
        )
        return child_page_ids

    async def delete_page_async(self, page_id: int) -> None:
        """Delete a single page by its id. Possible child pages are left intact.

        Arguments
        ---------
        page_id
            The id of the page to be deleted.

        Raises
        ------
        ConfluenceRESTAuthError
            If the access to the page is denied.

        ConfluenceRESTError
            If the deletion fails for any other reason.

        """
        try:
            url = self._make_url(self._root_url, f"wiki/api/v2/pages/{page_id}")
            async with self._client.delete(url) as response:
                response.raise_for_status()
                self._update_write_progress(True, f"id#{page_id}")

        except aiohttp.ClientResponseError as e:
            self._update_write_progress(False, f"id#{page_id}")
            if e.status == 401:
                raise ConfluenceRESTAuthError(
                    f"Access denied to page id#{page_id}. Check your credentials."
                ) from e
            elif e.status == 404:
                raise ConfluenceRESTNotFoundError(
                    f"Page id#{page_id} was not found."
                ) from e
            raise ConfluenceRESTError(
                f"Failed to delete page id#{page_id}. HTTP/{e.status}."
            ) from e

    async def get_space_id_async(self, space_key: str) -> int | None:
        """Get the id of the space.

        Arguments
        ---------
        space_key
            The key of the space.

        Returns
        -------
        int
            The id of the space. If the space is not found, None is returned.
        """
        api_endpoint = self._make_url(self._root_url, "wiki/api/v2/spaces")
        async with self._client.get(
            api_endpoint, params={"keys": space_key}
        ) as response:
            response.raise_for_status()
            space_id: int | None = None
            if results := (await response.json())["results"]:
                space_id = results[0]["id"]
            if not space_id:
                raise ConfluenceRESTNotFoundError(
                    "Couldn't resolve an id for Confluence space key "
                    + f"'{space_key}'. Check the space key, credentials, "
                    + "and permissions."
                )
            return space_id

    async def new_page_async(
        self, space_id, page_title, page_content, parent_id=None
    ) -> int | None:
        """Create a new page.

        Arguments
        ---------
        space_id
            The id of the space where the page will be created.
        page_title
            The title of the page.
        page_content
            The content of the page. Can be either simple HTML or
            Confluence Storage Format.
        parent_id
            The id number of the page whose child the page should be.
            If this is None, the page is created into the root of the
            space.

        Returns
        -------
        int
            The id of the created page. If the creation fails, None is returned.
        """

        data = {
            "spaceId": space_id,
            "status": "current",
            "title": page_title,
            "body": {"representation": "storage", "value": page_content},
        }

        if parent_id:
            data["parentId"] = parent_id

        api_endpoint = self._make_url(self._root_url, "wiki/api/v2/pages")
        async with self._client.post(api_endpoint, data=json.dumps(data)) as response:
            response.raise_for_status()
            page_id: int | None = None
            if results := (await response.json()):
                page_id = results["id"]
            self._update_write_progress(page_id is not None, page_title)
            return page_id

    async def get_page_id_async(self, space_id: int, page_title: str) -> int | None:
        """Get the id of the page in given space with given title.

        Page titles are unique inside a space.

        Arguments
        ---------
        space_id
            The id of the space the page is in.
        page_title
            The title of the page.

        Returns
        -------
        int
            The id of the page. If the page is not found, None is returned.
        """
        url = self._make_url(self._root_url, "wiki/api/v2/pages")

        async with self._client.get(
            url, params={"title": page_title, "space-id": [space_id]}
        ) as response:
            page_id: int | None = None
            if response.status == 200:
                if results := (await response.json())["results"]:
                    page_id = results[0]["id"]
            return page_id

    async def get_permitted_operations_on_resource_async(
        self, resource_type: ConfluenceResourceType, resource_id: int
    ) -> dict:
        """Get allowed operations for a Confluence resource.

        Arguments
        ---------
        resource_type
            The type of the resource.
        resource_id
            The id of the resource.

        Returns
        -------
        dict
            The permissions of the resource.
        """

        if resource_type not in ConfluenceResourceType:
            raise ValueError(f"Invalid resource type: {resource_type}")

        if resource_type == ConfluenceResourceType.PAGE:
            url = self._make_url(
                self._root_url, f"wiki/api/v2/pages/{resource_id}/operations"
            )
        elif resource_type == ConfluenceResourceType.SPACE:
            url = self._make_url(
                self._root_url, f"wiki/api/v2/spaces/{resource_id}/operations"
            )

        try:
            async with self._client.get(url) as response:
                response.raise_for_status()
                response_json = await response.json()
                allowed_ops = response_json["operations"]
                return allowed_ops
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ConfluenceRESTAuthError(
                    f"Access denied to {resource_type.value} id#{resource_id}. Check your credentials."
                ) from e
            elif e.status == 404:
                raise ConfluenceRESTNotFoundError(
                    f"Can't find {resource_type.value} id#{resource_id} was not found."
                ) from e
            raise ConfluenceRESTError(
                f"Failed to fetch allowed ops for {resource_type.value} id#{resource_id}. HTTP/{e.status}."
            ) from e

    # TODO: remove this and use get_permitted_operations_on_resource_async instead
    async def test_space_access(self, space_key: str) -> bool:
        """Test if the Confluence is accessible with current crendentials.

        Arguments
        ---------
        space_key
            The key of the space.

        Returns
        -------
        bool
            True if the space is accessible, False otherwise.

        """
        url = self._make_url(self._root_url, "wiki/api/v2/spaces")
        async with self._client.get(url, params={"keys": space_key}) as response:
            if response.status == 200:
                return True
            return False

    async def update_page_async(
        self, page_id, page_title, page_content, parent_id=None
    ) -> int | None:
        """Update the title, content and/or parent of a page.

        Notice that this overwrites the previous contents of the page!

        Arguments
        ---------
        page_id
            The id number of the page to be updated.
        page_title
            The new title of the page. If the title isn't changed, the
            old title has to be given.
        page_content
            The content of the page. Can be either simple HTML or
            Confluence Storage Format.
        parent_id
            The new parent of page.

        Returns
        -------
        int
            The id of the updated page. If the update fails, None is returned.
        """
        new_page_status = "current"
        content_representation_type = "storage"

        page_version_api_url = self._make_url(
            self._root_url, f"wiki/api/v2/pages/{page_id}/versions"
        )
        async with self._client.get(
            page_version_api_url, params={"limit": 1, "sort": "-modified-date"}
        ) as response:
            response.raise_for_status()
            if results := (await response.json())["results"]:
                current_version = results[0]["number"]
                new_version = current_version + 1
            else:
                # self._update_write_progress(False)
                return None

        new_data = {
            "id": page_id,
            "status": new_page_status,
            "title": page_title,
            "body": {
                "representation": content_representation_type,
                "value": page_content,
            },
            "version": {"number": new_version},
        }
        if parent_id:
            new_data["parent_id"] = parent_id

        page_api_url = self._make_url(self._root_url, f"wiki/api/v2/pages/{page_id}")
        async with self._client.put(
            page_api_url, data=json.dumps(new_data)
        ) as response:
            response.raise_for_status()
            if results := (await response.json()):
                page_id = results["id"]
            self._update_write_progress(page_id is not None, page_title)
            return page_id

    async def upsert_page_async(
        self,
        page_title: str,
        page_content: str,
        space_id: str,
        parent_page_id: int | None = None,
    ) -> int:
        """Create a new page or update an existing page with the same title.

        If a page with the same title is found, it is updated. Otherwise a new
        page is created.

        Arguments
        ---------
        page_title
            The title of the page. This is unique inside a space.

        page_content
            The content of the page. Can be either simple HTML or
            Confluence Storage Format.

        space_id
            The id of the space where the page will be created.

        parent_page_id
            The id number of the page whose child the page should be.
            If this is None, the page is created into the root of the
            space.


        Returns
        -------
        int
            The id of the created or updated page.
        """
        page_id = await self.get_page_id_async(space_id, page_title)
        if page_id:
            page_id = await self.update_page_async(
                page_id,
                page_title,
                page_content,
                parent_id=parent_page_id,
            )
        else:
            page_id = await self.new_page_async(
                space_id, page_title, page_content, parent_id=parent_page_id
            )
        return page_id
