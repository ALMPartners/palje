from __future__ import annotations

# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

from enum import Enum
import json
from typing import Callable, Literal
import aiohttp
from urllib.parse import urljoin

from palje.confluence.confluence_models import ConfluencePage, ConfluencePageAttachment
from palje.confluence.confluence_rest_models import ConfluenceApiPageResult
from palje.confluence.confluence_types import ConfluencePageBodyFormat


# logging.basicConfig(level=logging.DEBUG)


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
        # TODO: check if default content-type could be overwritten later
        #       e.g. file uploads will break if set here (need multipart/form-data)
        # "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def __init__(
        self,
        root_url: str,
        user_id: str,
        api_token: str,
        headers: dict | None = None,
        request_limit: int = 0,
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

        request_limit
            The maximum number of simultaneous connections to be used in the aiohttp
            client. High number of connections may cause HTTP/500s. Value
            of zero or less is interpreted as no limit (default).

        progress_callback
            Optional callback function that is called after each request.
            The callback function should accept [bool, str] params.
            The first one indicates if the request was succesfully completed, and
            the latter may contain some details about the operation.

        """

        self._root_url = root_url
        if headers is None:
            headers = self._DEFAULT_HEADERS

        if request_limit > 0:
            self._client = aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(login=user_id, password=api_token),
                headers=headers,
                connector=aiohttp.TCPConnector(limit=request_limit),
            )
        else:
            self._client = aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(login=user_id, password=api_token),
                headers=headers,
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

    async def move_page_async(
        self,
        page_id: int,
        before_or_after: Literal["before", "after"],
        target_page_id: int,
    ) -> None:
        """Move a page before or after another page.

        Arguments
        ---------

        page_id: int
            The id of the page to be moved.

        before_or_after: str
            The position where the page will be moved. Must be either
            "before" or "after".

        target_page_id: int
            The id of the target page.

        Raises
        ------

        ValueError
            If the before_or_after argument is invalid.

        """

        if before_or_after not in ["before", "after"]:
            raise ValueError(f"Invalid value for before_or_after: {before_or_after}")

        url = self._make_url(
            self._root_url,
            f"wiki/rest/api/content/{page_id}/move/{before_or_after}/{target_page_id}",
        )

        async with self._client.put(
            url,
            headers={"Content-Type": "application/json"},
        ) as response:
            response.raise_for_status()
            return

    async def get_child_pages_async(
        self, parent_page_id: int
    ) -> list[ConfluenceApiPageResult]:
        """Get the child pages of the given page. This is not recursive i.e.
        only the direct children of the page are returned. Due to Confluence having a
        limit (250) on the number of results per response, this method may make multiple
        requests.

        Arguments
        ---------
        parent_page_id
            The id of the parent page.

        Returns
        -------
        list[ConfluenceChildPageResult]
            A list of the child pages. If the parent page
            has no children, an empty list is returned.
        """

        # See the current max limit for results:
        # https://developer.atlassian.com/cloud/confluence/rest/api-group-content/#api-api-content-id-child-get
        MAX_RESULTS = 250

        url = self._make_url(
            self._root_url,
            f"wiki/api/v2/pages/{parent_page_id}/children?limit={MAX_RESULTS}",
        )

        has_more_children = True
        child_page_results = []

        while has_more_children:
            try:
                async with self._client.get(url) as response:
                    response.raise_for_status()
                    if response_json := (await response.json()):
                        child_page_results.extend(
                            [
                                ConfluenceApiPageResult.from_dict(result)
                                for result in response_json["results"]
                            ]
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
            True, f"page#{parent_page_id} has {len(child_page_results)} child pages"
        )
        return child_page_results

    async def delete_page_async(self, page: ConfluencePage) -> None:
        """Delete a single page from Confluence. Possible child pages are left intact.

        Arguments
        ---------
        ConfluencePage
            ConfluencePage that identifies the page to be deleted.

        Raises
        ------
        ConfluenceRESTAuthError
            If the access to the page is denied.

        ConfluenceRESTError
            If the deletion fails for any other reason.

        """
        try:
            url = self._make_url(self._root_url, f"wiki/api/v2/pages/{page.id}")
            async with self._client.delete(url) as response:
                response.raise_for_status()
                self._update_write_progress(True, str(page))

        except aiohttp.ClientResponseError as e:
            self._update_write_progress(False, str(page))
            if e.status == 401:
                raise ConfluenceRESTAuthError(
                    f"Access denied to page '{str(page)}'. Check your credentials."
                ) from e
            elif e.status == 404:
                raise ConfluenceRESTNotFoundError(
                    f"Page id#{page.id} was not found."
                ) from e
            raise ConfluenceRESTError(
                f"Failed to delete page '{str(page)}'. HTTP/{e.status}."
            ) from e

    async def get_space_id_async(self, space_key: str) -> int | None:
        """Get the id for given Confluence space key.

        Arguments
        ---------
        space_key
            The key of the space.

        Returns
        -------
        int
             The id of the space. If the space is not found, None is returned.
        """
        try:
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
                        "Couldn't resolve id for Confluence space "
                        + f"'{space_key}'. Check the space key, credentials, "
                        + "and permissions."
                    )
                return space_id
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ConfluenceRESTAuthError(
                    f"Access denied. Check your credentials."
                ) from e
            elif e.status == 404:
                raise ConfluenceRESTNotFoundError(
                    f"Space was not found or not accessible with given credentials."
                ) from e
            raise ConfluenceRESTError(
                f"Couldn't fetch space id for '{space_key}'. HTTP/{e.status}."
            ) from e

    async def new_page_async(
        self, space_id, page_title, page_content, parent_id=None
    ) -> int | None:
        """Create a new Confluence page.

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
        async with self._client.post(
            api_endpoint,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        ) as response:
            response.raise_for_status()
            page_id: int | None = None
            if results := (await response.json()):
                page_id = results["id"]
            self._update_write_progress(page_id is not None, page_title)
            return page_id

    # FIXME: refactor duplicate code with get_page_by_title_async
    # Notice that while DELETE /pages/:id could be used here, it would need
    # status filtering to avoid returning "trashed" and similar pages.
    async def get_page_by_id_async(
        self, page_id: int
    ) -> ConfluenceApiPageResult | None:
        """Get the page in given space by its ID.

        Arguments
        ---------
        page_id
            The id of the page.

        Returns
        -------
        ConfluenceApiPageResult
            Details of found page.

        Raises
        ------
        ConfluenceRESTNotFoundError
            If the page is not found.

        ConfluenceRESTAuthError
            If access to the page is denied.

        ConfluenceRESTError
            If the request fails for any other reason.
        """
        url = self._make_url(self._root_url, f"wiki/api/v2/pages")

        try:
            async with self._client.get(url, params={"id": [page_id]}) as response:
                response.raise_for_status()
                if results := (await response.json())["results"]:
                    return ConfluenceApiPageResult.from_dict(results[0])
                raise ConfluenceRESTNotFoundError(f"Can't find page id#{page_id}.")
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ConfluenceRESTAuthError(
                    f"Access denied to page id#{page_id}. Check your credentials."
                ) from e
            raise ConfluenceRESTError(
                f"Failed to fetch page id#{page_id}. HTTP/{e.status}."
            ) from e

    async def get_page_by_title_async(
        self,
        space_id: int,
        page_title: str,
        body_format: ConfluencePageBodyFormat = ConfluencePageBodyFormat.STORAGE,
    ) -> ConfluenceApiPageResult:
        """Get the page in given space with given title.

        Page titles are unique inside a space.

        Arguments
        ---------
        space_id
            The id of the space the page is in.
        page_title
            The title of the page.
        body_format:
            The format of the page body to be returned. Default NONE means that
            the body content is not returned.

        Returns
        -------
        ConfluenceApiPageResult
            Details of found page.

        Raises
        ------
        ConfluenceRESTNotFoundError
            If the page is not found.

        ConfluenceRESTAuthError
            If access to the page is denied.

        ConfluenceRESTError
            If the request fails for any other reason.
        """
        url = self._make_url(self._root_url, "wiki/api/v2/pages")

        try:
            params = {"title": page_title, "space-id": space_id}
            if body_format != ConfluencePageBodyFormat.NONE:
                params["body-format"] = body_format.value
            async with self._client.get(url, params=params) as response:
                response.raise_for_status()
                if response.status == 200:
                    if results := (await response.json())["results"]:
                        return ConfluenceApiPageResult.from_dict(results[0])
                    else:
                        # Both /pages and /spaces/:key/pages apis seem to return
                        # HTTP/200 for missing pages instead of HTTP/404
                        raise ConfluenceRESTNotFoundError(
                            f"Can't find page '{page_title}' from space id#{space_id}."
                        )
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise ConfluenceRESTAuthError(
                    f"Access denied to page '{page_title}' in space id#{space_id}."
                    + " Check your credentials."
                ) from e
            raise ConfluenceRESTError(
                f"Failed to fetch page '{page_title}' in space id#{space_id}."
                + f" HTTP/{e.status}."
            ) from e

    # TODO: remove this and use get_page_by_title_async instead
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

    async def get_pages_in_space_async(
        self, space_id: int
    ) -> list[ConfluenceApiPageResult]:
        """Get all pages in a Confluence space.

        Arguments
        ---------
        space_id
            The id of the space.

        Returns
        -------
        list[ConfluenceApiPageResult]
            A list of the pages in the space.
        """
        url = self._make_url(self._root_url, f"wiki/api/v2/spaces/{space_id}/pages")
        params = {"limit": 250}
        has_more = True
        page_results = []

        while has_more:
            async with self._client.get(url, params=params) as response:
                response.raise_for_status()
                response_json = await response.json()
                results = response_json["results"]
                page_results.extend(
                    [ConfluenceApiPageResult.from_dict(result) for result in results]
                )
                if "_links" in response_json and "next" in response_json["_links"]:
                    url = self._make_url(
                        self._root_url, response_json["_links"]["next"]
                    )
                else:
                    has_more = False
        return page_results

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
                    f"Can't find {resource_type.value} id#{resource_id}."
                ) from e
            raise ConfluenceRESTError(
                f"Failed to fetch allowed ops for {resource_type.value} id#{resource_id}. HTTP/{e.status}."
            ) from e

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
            page_version_api_url,
            params={"limit": 1, "sort": "-modified-date"},
            headers={"Content-Type": "application/json"},
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
            page_api_url,
            data=json.dumps(new_data),
            headers={"Content-Type": "application/json"},
        ) as response:
            response.raise_for_status()
            if results := (await response.json()):
                page_id = results["id"]
            self._update_write_progress(page_id is not None, page_title)
            return page_id

    # region Attachments

    async def get_page_attachments(self, page_id: int) -> list:
        """Get the attachments of a page.

        Arguments
        ---------
        page_id
            The id of the page.

        Returns
        -------
        list
            A list of the attachments of the page.
        """
        url = self._make_url(self._root_url, f"wiki/api/v2/pages/{page_id}/attachments")
        async with self._client.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def upsert_page_attachment_async(
        self, page_id: int, attachment: ConfluencePageAttachment
    ) -> int:
        """Add or update file attachment in given page.

            Notice: Implemented with Confluence REST API v1. This may get deprecated at
            some point. At the time of writing, REST API v2 does not support adding
            attachments to a page (yet).

        Parameters
        ---------
        attachment: ConfluencePageAttachment
            The attachment to be added.

        Returns
        -------
        int
            The id of the attachment.
        """

        headers = self._DEFAULT_HEADERS.copy()
        headers["X-Atlassian-Token"] = "nocheck"
        url = self._make_url(
            self._root_url, f"/wiki/rest/api/content/{page_id}/child/attachment"
        )

        with open(attachment.file_path, "rb") as file:
            form_data = aiohttp.FormData()

            form_data.add_field(
                "file",
                file,
                filename=attachment.title,
                content_type=attachment.content_type,
            )

            async with self._client.put(
                url, data=form_data, headers=headers
            ) as response:
                response.raise_for_status()
                json_resp = await response.json()
                return json_resp["results"][0]["id"]

    async def download_file_async(self, rel_download_path: str) -> bytes:
        """Download a file and return it as bytes. Meant for downloading Confluence page
           attachments, not tested for other purposes.

        Arguments
        ---------
        dowload_link
            The link to the file in Confluence to be downloaded.

        Returns
        -------
        bytes
            The content of the file.
        """
        url = self._make_url(self._root_url, f"wiki/{rel_download_path}")
        async with self._client.get(url) as resp:
            assert resp.status == 200
            return await resp.read()

    # endregion Attachments

    async def create_page_async(self, space_id: int, page: ConfluencePage) -> int:
        """Create a new page"""
        parent_id: int | None = page.parent_page.id if page.parent_page else None
        page_id = await self.new_page_async(
            space_id, page.title, page.body_content, parent_id=parent_id
        )

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
