"""Routes and logic for HTTP test server."""
import json
from base64 import b64decode

from test.conftest import TEST_DB_NAME

TEST_URL = "http://localhost:10300/"

AVAILABLE_USERS = [{"user": "test", "password": "Test123"},
                   {"user": "Salla", "password": "ALM Partners"}]

AVAILABLE_PAGES = [{"space-id": "1", 'title': "test", "id": 1234, "version": 3},
                   {"space-id": "1", 'title': "test2", "id": 666},
                   {"space-id": "1", 'title': f"{TEST_DB_NAME}.store", "id": 1, "version": 3},
                   {"space-id": "1", 'title': f"Tables {TEST_DB_NAME}.store", "id": 2, "version": 1},
                   {"space-id": "1", 'title': f"{TEST_DB_NAME}.store.Clients", "id": 3, "version": 1},
                   {"space-id": "1", 'title': f"{TEST_DB_NAME}.store.Products", "id": 4, "version": 1},
                   {"space-id": "1", 'title': f"{TEST_DB_NAME}.report", "id": 5, "version": 3},
                   {"space-id": "1", 'title': f"Tables {TEST_DB_NAME}.report", "id": 6, "version": 1},
                   {"space-id": "1", 'title': f"{TEST_DB_NAME}.report.ProductWeekly", "id": 7, "version": 1},
                   {"space-id": "1", 'title': f"Procedures {TEST_DB_NAME}.store", "id": 8, "version": 1},
                   {"space-id": "1", 'title': f"{TEST_DB_NAME}.store.spSELECT", "id": 9, "version": 1}]


def test_auth(request):
    auth = request.get('headers', {}).get('Authorization')
    if auth:
        decoded_auth = b64decode(auth[6:]).decode()
        user, password = decoded_auth.split(":")
        for available in AVAILABLE_USERS:
            if user == available['user'] and password == available['password']:
                return json.dumps({"results": "OK"})
    raise Exception("Unauthorized")    # status code 500

def get_page_version(request):
    path = request.get('path')
    page_id = path.split('/')[-2]
    for available in AVAILABLE_PAGES:
        if int(page_id) == available["id"] and available.get('version'):
            return json.dumps({'results' : [{'number': available["version"]}]})
    raise Exception('Page not found')    # status code 500

def get_page_id(request):
    query_params = request.get('query_params')
    query_params['title'] = query_params['title'].replace('+', ' ')    # '+' is whitespace
    for available in AVAILABLE_PAGES:
        if all(item in available.items() for item in query_params.items()):
            return json.dumps({"results": [{"id": available["id"]}]})
    return json.dumps({"results": []})    # no page found

def post_content(request):
    """Body should be
    {
        'title': 'title',
        'spaceId': space_id,
        'body': {
            'representation': 'storage',
            'value': 'value'},
        'parentId': parent_id    (optional)
    }
    """
    body = request["body"]
    if not all(key in body for key in ('title', 'spaceId', 'body')):
        raise Exception('Missing keys from body')
    if not all(key in body.get('body') for key in ('value', 'representation')):
        raise Exception('Missing keys from body')
    for available in AVAILABLE_PAGES:
        if available['title'] == body.get('title'):
            raise Exception('Page already exists')
    return json.dumps({"id": "69"})


def put_content(request):
    """Body should be
    {
        'type': 'page',
        'title': 'title',
        'body': {'storage': {'value': 'value', 'representation': 'storage'}},
        'version' : {'number': number},
        'ancestors': [{'id': parent_id}]    (optional)
    }
    """
    body = request["body"]
    if not all(key in body for key in ('id', 'status', 'title', 'body', 'version')):
        raise Exception('Missing keys from body')
    if not all(key in body.get('body') for key in ('value', 'representation')):
        raise Exception('Missing keys from body')
    return json.dumps({"result": "OK"})


ROUTES = {
    "GET": {
        "/wiki/": test_auth,
        "/wiki/api/v2/pages": get_page_id,
        "/wiki/api/v2/pages/1234/versions": get_page_version,
        "/wiki/api/v2/pages/666/versions": get_page_version,
        "/wiki/api/v2/pages/1/versions": get_page_version,
        "/wiki/api/v2/pages/2/versions": get_page_version,
        "/wiki/api/v2/pages/3/versions": get_page_version,
        "/wiki/api/v2/pages/4/versions": get_page_version,
        "/wiki/api/v2/pages/5/versions": get_page_version,
        "/wiki/api/v2/pages/6/versions": get_page_version,
        "/wiki/api/v2/pages/7/versions": get_page_version,
        "/wiki/api/v2/pages/8/versions": get_page_version,
        "/wiki/api/v2/pages/9/versions": get_page_version,
        "/wiki/api/v2/spaces": test_auth
    },
    "POST": {
        "/wiki/api/v2/pages": post_content
    },
    "PUT": {
        "/wiki/api/v2/pages/1234/": put_content,
        "/wiki/api/v2/pages/666/": put_content,
        "/wiki/api/v2/pages/1/": put_content,
        "/wiki/api/v2/pages/2/": put_content,
        "/wiki/api/v2/pages/3/": put_content,
        "/wiki/api/v2/pages/4/": put_content,
        "/wiki/api/v2/pages/5/": put_content,
        "/wiki/api/v2/pages/6/": put_content,
        "/wiki/api/v2/pages/7/": put_content,
        "/wiki/api/v2/pages/8/": put_content,
        "/wiki/api/v2/pages/9/": put_content
    }

}
