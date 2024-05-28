import pytest
from palje.confluence_rest import ConfluenceREST, ConfluenceRESTError

from test.routes import AVAILABLE_PAGES, AVAILABLE_USERS, TEST_URL

@pytest.mark.http_server
class TestWithHTTPServer():

    @pytest.fixture(scope='function', autouse=True)
    def confluence_rest_init(self):
        self.wiki = ConfluenceREST(atlassian_url=TEST_URL)
        yield

    @pytest.mark.parametrize("credentials", AVAILABLE_USERS)
    def test_login_should_succeed_for_available_user(self, credentials):
        self.wiki.test_confluence_access(confluence_user_id=credentials['user'], confluence_api_token=credentials['password'], space_key='TEST')

    def test_login_should_fail_for_unavailable_user(self):
        credentials = {'user': 'Salla', 'password': 'tyhja'}
        with pytest.raises(ConfluenceRESTError) as e:
            self.wiki.test_confluence_access(confluence_user_id=credentials['user'], confluence_api_token=credentials['password'], space_key='TEST')

    @pytest.mark.parametrize("page", AVAILABLE_PAGES[:2])
    def test_id_should_be_returned_for_available_page(self, page):
        page_id = self.wiki.get_page_id(page['space-id'], page['title'])
        assert page_id == page['id']

    def test_None_should_be_returned_for_unavailable_page(self):
        page = {"space-id": "TEST", 'title': "does_not_exists", "id": None}
        page_id = self.wiki.get_page_id(page['space-id'], page['title'])
        assert page_id == page['id']

    def test_new_page_should_succeed_if_page_does_not_exist(self, capsys):
        page = {"space-id": "1", 'title': "does_not_exists"}
        self.wiki.new_page(page['space-id'], page['title'], 'moi')
        captured = capsys.readouterr()
        assert f"Page {page['title']} created." in captured.out

    @pytest.mark.parametrize("page", AVAILABLE_PAGES[:2])
    def test_new_page_should_fail_if_title_exists(self, page, capsys):
        self.wiki.new_page(page['space-id'], page['title'], 'moi')
        captured = capsys.readouterr()
        assert f"Failed to create page {page['title']}." in captured.out

    @pytest.mark.parametrize("page", AVAILABLE_PAGES[:2])
    def test_page_update_should_fail_if_version_cannot_be_fetched(self, page, capsys):
        # can be fetched
        if page.get('version'):
            self.wiki.update_page(page['id'], page['title'], 'moi')
            captured = capsys.readouterr()
            assert f"Page {page['title']} updated." in captured.out
        # cannot be fetched
        else:
            self.wiki.update_page(page['id'], page['title'], 'moi')
            captured = capsys.readouterr()
            assert f"Failed to retrieve the version number of page {page['title']}." in captured.out
