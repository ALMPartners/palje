"""Routes and logic for HTTP test server."""
import json
from base64 import b64decode

from .conftest import TEST_DB_NAME

TEST_URL = "http://localhost:10300/wiki/rest/api/content"

AVAILABLE_USERS = [{"user": "test", "password": "Test123"},
                   {"user": "Salla", "password": "ALM Partners"}]

AVAILABLE_PAGES = [{"spaceKey": "TEST", 'title': "test", "id": 1234, "version": 3},
                   {"spaceKey": "TEST", 'title': "test2", "id": 666},
                   {"spaceKey": "TEST", 'title': f"{TEST_DB_NAME}.store", "id": 1, "version": 3},
                   {"spaceKey": "TEST", 'title': f"Tables {TEST_DB_NAME}.store", "id": 2, "version": 1},
                   {"spaceKey": "TEST", 'title': f"{TEST_DB_NAME}.store.Clients", "id": 3, "version": 1},
                   {"spaceKey": "TEST", 'title': f"{TEST_DB_NAME}.store.Products", "id": 4, "version": 1},
                   {"spaceKey": "TEST", 'title': f"{TEST_DB_NAME}.report", "id": 5, "version": 3},
                   {"spaceKey": "TEST", 'title': f"Tables {TEST_DB_NAME}.report", "id": 6, "version": 1},
                   {"spaceKey": "TEST", 'title': f"{TEST_DB_NAME}.report.ProductWeekly", "id": 7, "version": 1},
                   {"spaceKey": "TEST", 'title': f"Procedures {TEST_DB_NAME}.store", "id": 8, "version": 1},
                   {"spaceKey": "TEST", 'title': f"{TEST_DB_NAME}.store.spSELECT", "id": 9, "version": 1}]


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
    page_id = path.split('/')[-1]
    for available in AVAILABLE_PAGES:
        if int(page_id) == available["id"] and available.get('version'):
            return json.dumps({'version' : {'number': available["version"]}})
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
        'type': 'page',
        'title': 'title',
        'space': {'key': 'spake_key'},
        'body': {'storage': {'value': 'value', 'representation': 'storage'}},
        'ancestors': [{'id': parent_id}]    (optional)
    }
    """
    body = request["body"]
    if not all(key in body for key in ('type', 'title', 'space', 'body')):
        raise Exception('Missing keys from body')
    if "key" not in body.get('space') and "storage" not in body.get('body'):
        raise Exception('Missing keys from body')
    if not all(key in body.get('body').get('storage') for key in ('value', 'representation')):
        raise Exception('Missing keys from body')
    for available in AVAILABLE_PAGES:
        if available['title'] == body.get('title'):
            raise Exception('Page already exists')
    return json.dumps({"result": "OK"})


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
    if not all(key in body for key in ('type', 'title', 'body', 'version')):
        raise Exception('Missing keys from body')
    if "storage" not in body.get('body') and "number" not in body.get('version'):
        raise Exception('Missing keys from body')
    if not all(key in body.get('body').get('storage') for key in ('value', 'representation')):
        raise Exception('Missing keys from body')
    return json.dumps({"result": "OK"})


ROUTES = {
    "GET": {
        "/wiki/rest/api/space": test_auth,
        "/wiki/rest/api/content": get_page_id,
        "/wiki/rest/api/content/1234": get_page_version,
        "/wiki/rest/api/content/666": get_page_version,
        "/wiki/rest/api/content/1": get_page_version,
        "/wiki/rest/api/content/2": get_page_version,
        "/wiki/rest/api/content/3": get_page_version,
        "/wiki/rest/api/content/4": get_page_version,
        "/wiki/rest/api/content/5": get_page_version,
        "/wiki/rest/api/content/6": get_page_version,
        "/wiki/rest/api/content/7": get_page_version,
        "/wiki/rest/api/content/8": get_page_version,
        "/wiki/rest/api/content/9": get_page_version
    },
    "POST": {
        "/wiki/rest/api/content": post_content
    },
    "PUT": {
        "/wiki/rest/api/content/1234": put_content,
        "/wiki/rest/api/content/666": put_content,
        "/wiki/rest/api/content/1": put_content,
        "/wiki/rest/api/content/2": put_content,
        "/wiki/rest/api/content/3": put_content,
        "/wiki/rest/api/content/4": put_content,
        "/wiki/rest/api/content/5": put_content,
        "/wiki/rest/api/content/6": put_content,
        "/wiki/rest/api/content/7": put_content,
        "/wiki/rest/api/content/8": put_content,
        "/wiki/rest/api/content/9": put_content
    }

}
