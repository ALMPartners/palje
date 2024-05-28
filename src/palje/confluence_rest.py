# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

import json
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError


class ConfluenceRESTError(Exception):
    """Generic Confluence related exception"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class ConfluenceRESTAuthError(ConfluenceRESTError):
    """Generic Confluence related exception"""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

HEADERS = {"Content-type": "application/json"}

# TODO: wrap exceptions into ConfluenceRESTErrors (and subclasses) to avoid requests imports in the main code
# TODO: use logging instead of print

class ConfluenceREST:
    """Class for confluence REST API tools.

    Arguments
    ---------
    atlassian_url
        URL to Atlassian root page. The form is
        https://<yourconfluence>.atlassian.net/.

    Attributes
    ----------
    name
        Network location part from atlassian_url.
        Empty if not present.
    headers
        HTTP header to a request.
    auth
        Authentication tuple to a request.
    """

    _confluence_user_id: str
    _confluence_api_token: str

    def __init__(self, atlassian_url: str):
        # TODO: take creds as params
        self.wiki_root_url = urljoin(atlassian_url, "wiki/")
        self.name = atlassian_url
        self.headers = HEADERS
        self._confluence_user_id = ""
        self._confluence_api_token = ""

    def test_confluence_access(
        self, confluence_user_id: str, confluence_api_token: str, space_key: str
    ) -> bool:
        """Test if the Confluence space is accessible with given crendentials."""

        # TODO: test with set credentials instead of params
        url = urljoin(self.wiki_root_url, "api/v2/spaces")
        auth = HTTPBasicAuth(username=confluence_user_id, password=confluence_api_token)
        headers = {"Accept": "application/json"}
        try:
            response = requests.request(
                "GET", url, params={"keys": [space_key]}, headers=headers, auth=auth
            )
            response.raise_for_status()
            if len(response.json()["results"]) == 0:
                raise ConfluenceRESTAuthError("No accessible space was found with the given key.")
            return True
        except HTTPError as err:
            raise ConfluenceRESTError(str(err)) from err

    @property
    def auth(self) -> tuple[str, str]:
        return (self._confluence_user_id, self._confluence_api_token)

    @auth.setter
    def auth(self, values: tuple[str, str]):
        self._confluence_user_id = values[0]
        self._confluence_api_token = values[1]

    @property
    def user_id(self) -> str:
        return self._confluence_user_id

    @user_id.setter
    def user_id(self, value):
        self._confluence_user_id = value

    @property
    def api_token(self) -> str:
        return self._confluence_api_token

    @api_token.setter
    def api_token(self, value):
        self._confluence_api_token = value


    def get_space_id(self, space_key):
        """Return the id of the space or None.

        Arguments
        ---------
        space_key
            The key of the space.
        """
        url = urljoin(self.wiki_root_url, "api/v2/spaces")
        response = requests.get(url, params={"keys": [space_key]}, auth=self.auth)
        response.raise_for_status()
        if results := response.json()["results"]:
            return results[0]["id"]
        return None

    def get_page_id(self, space_id, page_title):
        """Return the id of the page or None if no page is found.

        Page titles are unique inside a space.

        Arguments
        ---------
        space_id
            The id of the space the page is in.
        page_title
            The title of the page.
        """
        url = urljoin(self.wiki_root_url, "api/v2/pages")
        response = requests.get(
            url, params={"title": page_title, "space-id": [space_id]}, auth=self.auth
        )
        try:
            response.raise_for_status()
            if results := response.json()["results"]:
                return results[0]["id"]
            return None
        except HTTPError as err:
            print(f"Failed to retrieve the id of the page {page_title}.")
            print(f"Response: {err.response.text}")
            return None

    def new_page(self, space_id, page_title, page_content, parent_id=None):
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
        """
        url = urljoin(self.wiki_root_url, "api/v2/pages")
        data = {
            "title": page_title,
            "spaceId": space_id,
            "body": {"representation": "storage", "value": page_content},
        }
        if parent_id:
            data["parentId"] = parent_id
        response = requests.post(
            url, data=json.dumps(data), headers=self.headers, auth=self.auth
        )
        try:
            response.raise_for_status()
            print(f"Page {page_title} created.")
            return response.json()["id"]
        except HTTPError as err:
            print(f"Failed to create page {page_title}.")
            print(f"Response: {err.response.text}")

    def update_page(self, page_id, page_title, page_content, parent_id=None):
        """Update the title, content and/or parent of a page.

        Notice that this overwrites the previous contents of the page!

        Arguments
        ---------
        page_id
            The id number of the page.
        page_title
            The new title of the page. If the title isn't changed, the
            old title has to be given.
        page_content
            The content of the page. Can be either simple HTML or
            Confluence Storage Format.
        parent-id
            The new parent of page.
        """
        new_page_status = "current"
        content_representation_type = "storage"
        page_url = urljoin(self.wiki_root_url, f"api/v2/pages/{page_id}/")

        # get current version number
        versions_url = urljoin(page_url, "versions")
        response = requests.get(
            versions_url, params={"limit": 1, "sort": "-modified-date"}, auth=self.auth
        )

        try:
            response.raise_for_status()
            if results := response.json()["results"]:
                current_version = results[0]["number"]
                new_version = current_version + 1
            else:
                print(f"Failed to retrieve the version number of page {page_title}.")
                print(f"Cannot update page {page_title}.")
                return
        except HTTPError as err:
            print(f"Failed to retrieve the version number of page {page_title}.")
            print(f"Response: {err.response.text}")
            return

        # NEW CONTENT
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

        # UPDATE
        response = requests.put(
            page_url, data=json.dumps(new_data), headers=self.headers, auth=self.auth
        )
        try:
            response.raise_for_status()
            print(f"Page {page_title} updated.")
        except HTTPError as err:
            print(f"Failed to update page {page_title}.")
            print(f"Response: {err.response.text}")
