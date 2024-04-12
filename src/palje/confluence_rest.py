# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

import getpass
import json
from urllib.parse import urljoin

from requests import get, post, put
from requests.exceptions import HTTPError

HEADERS = {"Content-type": "application/json"}

class ConfluenceREST:
    '''Class for confluence REST API tools.

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
    '''

    def __init__(self, atlassian_url):
        self.wiki_root_url = urljoin(atlassian_url, 'wiki/')
        self.name = atlassian_url
        self.headers = HEADERS
        self.auth = ''

    def verify_credentials(self):
        '''Ask for credentials and check that they work.

        Ask the user for a username and API token for Confluence. Verify
        that the credentials work by sending a request to the wiki's
        root url. Quit palje if the login fails.
        '''
        uid = input(f"Confluence user for {self.name}: ")
        password = getpass.getpass(f"Atlassian API token for user {uid}: ")
        self.auth = (uid, password)
        try:
            response = get(self.wiki_root_url, auth=self.auth)
            response.raise_for_status()
            return True
        except Exception as err:
            print(err)
            print(f'Failed to login into Confluence {self.name}.' +
                  f' Check your username, password and Confluence URL.')
            quit()

    def get_space_id(self, space_key):
        '''Return the id of the space or None.

        Arguments
        ---------
        space_key
            The key of the space.
        '''
        url = urljoin(self.wiki_root_url, 'api/v2/spaces')
        response = get(
            url,
            params={'keys': [space_key]},
            auth=self.auth)
        response.raise_for_status()
        if results := response.json()['results']:
            return results[0]['id']
        return None

    def get_page_id(self, space_id, page_title):
        '''Return the id of the page or None if no page is found.

        Page titles are unique inside a space.

        Arguments
        ---------
        space_id
            The id of the space the page is in.
        page_title
            The title of the page.
        '''
        url = urljoin(self.wiki_root_url, 'api/v2/pages')
        response = get(
            url,
            params={
                'title': page_title,
                'space-id': [space_id]},
            auth=self.auth)
        try:
            response.raise_for_status()
            if results := response.json()['results']:
                return results[0]['id']
            return None
        except HTTPError as err:
            print(f'Failed to retrieve the id of the page {page_title}.')
            print(f'Response: {err.response.text}')
            return None

    def new_page(self, space_id, page_title, page_content, parent_id=None):
        '''Create a new page.

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
        '''
        url = urljoin(self.wiki_root_url, "api/v2/pages")
        data = {
            "title": page_title,
            "spaceId": space_id,
            "body": {
                "representation": "storage",
                "value": page_content}
        }
        if parent_id:
            data["parentId"] = parent_id
        response = post(
            url,
            data=json.dumps(data),
            headers=self.headers,
            auth=self.auth)
        try:
            response.raise_for_status()
            print(f'Page {page_title} created.')
            return response.json()['id']
        except HTTPError as err:
            print(f'Failed to create page {page_title}.')
            print(f'Response: {err.response.text}')

    def update_page(self, page_id, page_title, page_content, parent_id=None):
        '''Update the title, content and/or parent of a page.

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
        '''
        new_page_status = "current"
        content_representation_type = "storage"
        page_url = urljoin(self.wiki_root_url, f"api/v2/pages/{page_id}/")

        # get current version number
        versions_url = urljoin(page_url, 'versions')
        response = get(
            versions_url,
            params={'limit': 1, "sort": "-modified-date"},
            auth=self.auth)
        
        try:
            response.raise_for_status()
            if results := response.json()['results']:
                current_version = results[0]['number']
                new_version = current_version + 1
            else:
                print(f'Failed to retrieve the version number of page {page_title}.')
                print(f"Cannot update page {page_title}.")
                return
        except HTTPError as err:
            print(f'Failed to retrieve the version number of page {page_title}.')
            print(f'Response: {err.response.text}')
            return

        # NEW CONTENT
        new_data = {
            "id": page_id,
            "status": new_page_status,
            "title": page_title,
            "body": {
                "representation": content_representation_type,
                "value": page_content
            },
            "version": {"number": new_version}
        }
        if parent_id:
            new_data["parent_id"] = parent_id

        # UPDATE
        response = put(
            page_url,
            data=json.dumps(new_data),
            headers=self.headers,
            auth=self.auth)
        try:
            response.raise_for_status()
            print(f'Page {page_title} updated.')
        except HTTPError as err:
            print(f'Failed to update page {page_title}.')
            print(f'Response: {err.response.text}')
