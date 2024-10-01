import json
import aiohttp
from aiohttp.test_utils import RawTestServer
from aiohttp.web import Request, Response

TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 8080

VALID_CREDENTIALS = {"user": "tester@organization.org", "api_token": "test-token"}


class ConfluenceMockApi(RawTestServer):
    def __init__(self) -> None:
        super().__init__(
            handler=self.request_handler, host=TEST_SERVER_HOST, port=TEST_SERVER_PORT
        )

    @property
    def root_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def request_handler(self, request: Request) -> Response:
        """Request handler for aiohttp test server."""

        # Auth
        excepted_auth_header = aiohttp.BasicAuth(
            login=VALID_CREDENTIALS["user"], password=VALID_CREDENTIALS["api_token"]
        ).encode()
        if request.headers.get("Authorization") != excepted_auth_header:
            return Response(status=401)

        if request.method == "GET":
            match request.path:
                case "/wiki/api/v2/pages":
                    if (
                        request.query.get("space-id") == "existing_space_id"
                        and request.query.get("title") == "existing_page_title"
                    ):
                        resp_bytes = bytes(
                            json.dumps(valid_get_page_response), encoding="utf-8"
                        )
                        return Response(
                            body=resp_bytes, content_type="application/json"
                        )
                    else:
                        return Response(status=404)
                case "/wiki/api/v2/spaces":
                    if request.query.get("keys") == "existing_space_key":
                        return Response(
                            body=b'{"results": [{"id": "456"}]}',
                            content_type="application/json",
                            status=200,
                        )
                    else:
                        return Response(status=404)

        elif request.method == "POST":
            ...
            # return Response(status=201)
        return Response(status=404)


# region Confluence responses

valid_get_page_response = {
    "results": [
        {
            "id": "123",
            "status": "current",
            "title": "<string>",
            "spaceId": "<string>",
            "parentId": "<string>",
            "parentType": "page",
            "position": 57,
            "authorId": "<string>",
            "ownerId": "<string>",
            "lastOwnerId": "<string>",
            "createdAt": "<string>",
            "version": {
                "createdAt": "<string>",
                "message": "<string>",
                "number": 19,
                "minorEdit": True,
                "authorId": "<string>",
            },
            "body": {"storage": {}, "atlas_doc_format": {}},
            "_links": {"webui": "<string>", "editui": "<string>", "tinyui": "<string>"},
        }
    ],
    "_links": {"next": "<string>", "base": "<string>"},
}

# endregion
