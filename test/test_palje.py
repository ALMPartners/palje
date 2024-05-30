import pytest
from palje.__main__ import main

from test.routes import AVAILABLE_USERS, TEST_URL, TEST_DB_NAME


@pytest.mark.skip(reason="This test does not work due to changes to Confluence V2 API.")
@pytest.mark.mssql
@pytest.mark.http_server
def test_palje(mssql_config, mssql_credentials, monkeypatch, capsys):
    inputs = {
        f"Confluence user for {TEST_URL}: ": AVAILABLE_USERS[0]['user'],
        f"User for {mssql_config[0]}.{mssql_config[1]}. If you wish to use Windows Authentication, hit enter: ": mssql_credentials[0]
    }
    passwords = {
        f"Atlassian API token for user {AVAILABLE_USERS[0]['user']}: ": AVAILABLE_USERS[0]['password'],
        f"Password for user {mssql_credentials[0]}: ": mssql_credentials[1]}
    monkeypatch.setattr('builtins.input', lambda x: inputs[x])
    monkeypatch.setattr('getpass.getpass', lambda x: passwords[x])
    # run the actual integration test
    main([TEST_URL, "TEST",
          mssql_config[0], mssql_config[1],
          "--schemas", "store",
          "--db-driver", mssql_config[2],
          "--parent-page", "test"])
    captured = capsys.readouterr()
    assert 'Page test updated.' in captured.out
    assert f'Page {TEST_DB_NAME}.store updated.' in captured.out
    assert f'Page Tables {TEST_DB_NAME}.store updated.' in captured.out
    assert f'Page Procedures {TEST_DB_NAME}.store updated.' in captured.out
    assert f'Page {TEST_DB_NAME}.store.Clients updated.' in captured.out
    assert f'Page {TEST_DB_NAME}.store.Products updated.' in captured.out
    assert f'Page {TEST_DB_NAME}.store.spSELECT updated.' in captured.out
