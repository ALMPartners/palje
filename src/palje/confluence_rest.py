# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

import getpass
import json
from urllib.parse import urljoin, urlparse

from requests import get, post, put
from requests.exceptions import HTTPError

HEADERS = {"Content-type": "application/json"}

class ConfluenceREST:
    '''Class for confluence REST API tools.

    Arguments
    ---------
    content_url
        URL to Confluence REST content.
        The form is https://yourconfluence.atlassian.net/wiki/rest/api/content.

    Attributes
    ----------
    name
        Network location part from content_url.
        Empty if not present.
    headers
        HTTP header to a request.
    auth
        Authentication tuple to a request.
    '''

    def __init__(self, content_url):
        self.content_url = content_url
        self.name = self._get_confluence_name()
        self.headers = HEADERS
        self.auth = ''

    def _get_confluence_name(self):
        parsed = urlparse(self.content_url)
        return parsed[1]

    def login(self):
        '''Add the authentication tuple to an instance.
        Ask user for an username and password.
        Verify that the login with auth is successful.
        If login fails - quit.
        '''
        uid = input(f"Confluence user for {self.name}: ")
        password = getpass.getpass(f"Password for user {uid}: ")
        self.auth = (uid, password)
        # verify username and password
        url = urljoin(self.content_url, '.')
        try:
            r = get(urljoin(url, 'space'), auth=self.auth)
            r.raise_for_status()
            return True
        except:
            print(f'Failed to login into Confluence {self.name}. Check your username, password and Confluence URL.')
            quit()

    def get_page_id(self, space_key, page_title):
        '''Return the id of page. Return value is None if no page found.
        Notice that the name or title of the page is unique inside a space.

        Arguments
        ---------
        space_key
            The space key of the page.
        page_title
            The title of the page.
        '''
        r = get(self.content_url,
                            params={'title': page_title,
                                    'spaceKey': space_key},
                            auth=self.auth)
        try:
            r.raise_for_status()
            page_by_title = r.json()
            if page_by_title.get('results'):
                page_id = page_by_title['results'][0]['id']
                return page_id
            return None
        except HTTPError as err:
            print(f'Failed to retrieve the id of the page {page_title}.')
            print(f'Response: {err.response.text}')
            return None

    def new_page(self, space_key, page_title, page_content, parent_id=None):
        '''Create a new page.

        Arguments
        ---------
        space_key
            The space key of a new page.
        page_title
            The title of a new page.
        page_content
            Content of a new page. Can be simple HTML or Confluence Storage Format.
        parent_id
            The id number of the parent of a new page.
            If this is None, no parent is set to a new page.
        '''
        if parent_id:
            data = json.dumps({"type": "page",
                               "title": page_title,
                               "space": {"key": space_key},
                               "metadata": {
                                   "properties": {
                                       "content-appearance-draft": {"value": "full-width"},
                                       "content-appearance-published": {"value": "full-width"}
                                       }
                                    },
                               "body": {"storage": {"value": page_content, "representation": "storage"}},
                               "ancestors": [{"id": parent_id}]
                               })
        else:
            data = json.dumps({"type": "page",
                               "title": page_title,
                               "space": {"key": space_key},
                               "metadata": {
                                   "properties": {
                                       "content-appearance-draft": {"value": "full-width"},
                                       "content-appearance-published": {"value": "full-width"}
                                       }
                                    },
                               "body": {"storage": {"value": page_content, "representation": "storage"}}
                               })
        r = post(self.content_url,
                 data=data,
                 headers=self.headers,
                 auth=self.auth)
        try:
            r.raise_for_status()
            print(f'Page {page_title} created.')
        except HTTPError as err:
            print(f'Failed to create page {page_title}.')
            print(f'Response: {err.response.text}')

    def update_page(self, page_id, page_title, page_content, parent_id=None):
        '''Update page. The version number of the page is increased by one.
        Notice that this overwrites the previous contents of the page!

        Arguments
        ---------
        page_id
            The id number of the page.
        page_title
            The title of the page.
        page_content
            Content of the page. Can be simple HTML or Confluence Storage Format.
        parent-id
            The new parent of page.
        '''
        # get current version number
        page_url = urljoin(self.content_url + '/', str(page_id))
        v = get(page_url, auth=self.auth)
        try:
            v.raise_for_status()
            version = v.json()['version']['number'] + 1
        # If current version cannot be retrieved - abort.
        # Update won't succeed if version cannot be set correctly.
        except HTTPError as err:
            print(f'Update failed: failed to retrieve the version number of page {page_title}.')
            print(f'Response: {err.response.text}')
            return
        # NEW CONTENT
        if parent_id:
            new_data = json.dumps({"type": "page",
                                   "title": page_title,
                                   "body": {"storage": {"value": page_content, "representation": "storage"}},
                                   "ancestors": [{"id": parent_id}],
                                   "version": {"number": version}
                                   })
        else:
            new_data = json.dumps({"type": "page",
                                   "title": page_title,
                                   "body": {"storage": {"value": page_content, "representation": "storage"}},
                                   "version": {"number": version}
                                   })
        # UPDATE
        r = put(page_url,
                data=new_data,
                headers=self.headers,
                auth=self.auth)
        try:
            r.raise_for_status()
            print(f'Page {page_title} updated.')
        except HTTPError as err:
            print(f'Failed to update page {page_title}.')
            print(f'Response: {err.response.text}')
