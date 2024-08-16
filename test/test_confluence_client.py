import pytest

from palje.confluence.confluence_rest import ConfluenceRestClientAsync
from test.confluence_mock_api import VALID_CREDENTIALS, ConfluenceMockApi


# TODO:
# assert that custom exceptions are raised where appropriate
# Add more tests
# async def test_new_page_async__creates_new_page():
# async def test_new_page_async__fails_if_page_exists():
# async def test_update_page_async__updates_page():
# async def test_update_page_async__fails_if_page_does_not_exist():
# async def test_update_page_async__fails_if_version_cannot_be_fetched():


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return VALID_CREDENTIALS


@pytest.mark.skip(reason="Needs updating: test_space_access has been removed")
async def test_test_space_access_async__with_invalid_credentials__returns_false():
    async with ConfluenceMockApi() as api:
        async with ConfluenceRestClientAsync(
            root_url=api.root_url, user_id="invalid_user", api_token="invalid_token"
        ) as client:
            is_accessible = await client.test_space_access("existing_space_key")
            assert is_accessible == False


@pytest.mark.skip(reason="Needs updating: test_space_access has been removed")
async def test_test_space_access_async__with_valid_credentials__returns_true(
    valid_credentials,
):
    async with ConfluenceMockApi() as api:
        async with ConfluenceRestClientAsync(
            root_url=api.root_url,
            user_id=valid_credentials["user"],
            api_token=valid_credentials["api_token"],
        ) as client:
            is_accessible = await client.test_space_access("existing_space_key")
            assert is_accessible == True


async def test_get_page_id_async__finds_valid_page_id(valid_credentials):
    async with ConfluenceMockApi() as api:
        async with ConfluenceRestClientAsync(
            root_url=api.root_url,
            user_id=valid_credentials["user"],
            api_token=valid_credentials["api_token"],
        ) as client:
            page_id = await client.get_page_id_async(
                "existing_space_id", "existing_page_title"
            )
            assert page_id == "123"


async def test_get_page_id_async__returns_None_for_missing_page(valid_credentials):
    async with ConfluenceMockApi() as api:
        async with ConfluenceRestClientAsync(
            root_url=api.root_url,
            user_id=valid_credentials["user"],
            api_token=valid_credentials["api_token"],
        ) as client:
            page_id = await client.get_page_id_async(
                "existing_space_id", "NOT_existing_page_title"
            )
            assert page_id == None


async def test_get_space_id_async__finds_valid_space_id(valid_credentials):
    async with ConfluenceMockApi() as api:
        async with ConfluenceRestClientAsync(
            root_url=api.root_url,
            user_id=valid_credentials["user"],
            api_token=valid_credentials["api_token"],
        ) as client:
            space_id = await client.get_space_id_async(space_key="existing_space_key")
            assert space_id == "456"
