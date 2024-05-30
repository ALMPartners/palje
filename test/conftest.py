import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.sql import text

TEST_DB_NAME = 'PALJE_TEST'


def pytest_addoption(parser):
    parser.addoption(
        '--mssql_host',
        action='store',
        dest='mssql_host',
        help='SQL Server hostname used for tests.'
    )
    parser.addoption(
        '--mssql_port',
        action='store',
        default=1433,
        dest='mssql_port',
        help='SQL Server port number used for tests.'
    )
    parser.addoption(
        '--mssql_driver',
        action='store',
        default='ODBC Driver 17 for SQL Server',
        dest='mssql_driver',
        help='SQL Server ODBC driver name.'
    )
    parser.addoption(
        '--mssql_username',
        action='store',
        dest='mssql_username',
        default='',
        help='Username for SQL Server. Do not use for Win authentication.'
    )
    parser.addoption(
        '--mssql_password',
        action='store',
        dest='mssql_password',
        default='',
        help='Password for SQL Server. Do not use for Win authentication.'
    )

pytest_plugins = [
    "test.fixtures"
    ]

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "mssql: mark tests that require SQL server to run")
    config.addinivalue_line(
        "markers", "http_server: mark tests that require HTTP server to run")


def pytest_collection_modifyitems(config, items):
    """First, check if mssql tests can be executed, that is,
        - MSSQL hostname was given
        - connection to MSSQL can be established using the
            given hostname, port number, ODBC driver and credentials
        - MSSQL doesn't have database with name stored in constant TEST_DB_NAME

    If mssql tests can be executed, add fixture 'mssql_setup_and_teardown'
    to all tests marked with 'mssql'.

    If mssql tests can not be executed, skip tests marked with 'mssql'.

    For tests marked with 'http_server', add fixture 'http_server_setup_and_teardown'.
    """
    execute_mssql_tests = ensure_mssql_ready_for_tests(config)
    skip_mssql = pytest.mark.skip(reason="requires SQL Server")
    for item in items:
        if "mssql" in item.keywords:
            if execute_mssql_tests:
                # Add 'mssql_setup_and_teardown' as FIRST in fixture list
                fixtures = ['mssql_setup_and_teardown'] + item.fixturenames
                item.fixturenames = fixtures
            else:
                item.add_marker(skip_mssql)
        if "http_server" in item.keywords:
            item.fixturenames.append('http_server_setup_and_teardown')


def ensure_mssql_ready_for_tests(config):
    """Test connection to MSSQL instance
    and check the existence of database
    with name stored in constant TEST_DB_NAME.
    """
    try:
        if not config.getoption('mssql_host'):
            raise Exception('MSSQL Server not given')
        engine = engine_from(config)
        with engine.connect() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            query = text("SELECT name FROM sys.databases WHERE UPPER(name) = :name")
            result = connection.execute(query, {'name': TEST_DB_NAME})
        if result.fetchall():
            connection.execute(text(f'DROP DATABASE {TEST_DB_NAME}'))
        return True
    except:
        return False


def engine_from(config, database=None):
    if not database:
        database = 'master'
    connection_url = URL(
        drivername="mssql+pyodbc",
        username=config.getoption('mssql_username'),
        password=config.getoption('mssql_password'),
        host=config.getoption('mssql_host'),
        port=config.getoption('mssql_port'),
        database=database,
        query={'driver': config.getoption('mssql_driver')}
    )
    return create_engine(connection_url)
